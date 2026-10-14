from __future__ import annotations
import traceback
from pathlib import Path
from PySide6.QtCore import Qt,QThread,Signal,QTimer
from PySide6.QtGui import QAction,QIcon,QKeySequence,QShortcut,QGuiApplication
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QPushButton,QCheckBox,QComboBox,QListWidget,QSplitter,QScrollArea,QGroupBox,QLabel,QMessageBox,QFileDialog,QDialog,QDialogButtonBox,QSpinBox,QDoubleSpinBox,QTextBrowser,QProgressDialog,QMenu)
from .i18n import t,set_language,get_i18n
from .appearance import load_catalog,skin_by_id,qss_for_skin,icon_path,default_icon_for_skin
from .config import load_config,save_config,DEFAULT_ENGINE,ENGINE_LIMITS,resource_path,remember_geometry,stored_geometry,reset_geometries,clamp_geometry,valid_preprocess_strategy
from .fields import Field,empty_fields,auto_page_plan,remember_applied_value,field_choice_items
from .pdf_io import PdfDocument
from .preview import PreviewView
from .profiles import save_profile,load_profile,convert_page_value,PAGE_UNIT_MM,resolve_output_dir
from .naming import expand_template,sanitize_filename,build_filename,is_counter_template,expression_issue,expand_template_safe
from .pattern_dsl import find_all,pattern_issue
from .ocr_engine import recognize_field,OCR_STRATEGIES
from .app_logging import LOGGER,LOG_LEVEL_NAMES,default_log_levels,normalize_log_levels

class EngineWarmupWorker(QThread):
    completed=Signal(str)
    def __init__(self,name,engine=None):super().__init__(); self.name=name; self.engine=dict(engine or {})
    def run(self):
        try:
            from .ocr_engine import preload_backend
            lang=next((key for key in ("eslav","latin","chinese") if self.engine.get("lang_"+key)),"eslav")
            preload_backend(self.name,self.engine,lang); self.completed.emit("")
        except Exception as exc:
            LOGGER.exception("OCR engine preload failed")
            self.completed.emit(str(exc))

class RecognitionWorker(QThread):
    completed=Signal(int,object,str)
    def __init__(self,path,page,fields,engine,ocr_enabled,target_ids=None,textful=None):
        super().__init__(); import copy; self.path=Path(path); self.page=page; self.fields=copy.deepcopy(fields); self.engine=dict(engine); self.ocr_enabled=ocr_enabled; self.ocr_expression=target_ids is not None; self.target_ids=set(target_ids or [f.id for f in fields]); self.textful=list(textful) if textful is not None else None
    def run(self):
        LOGGER.info("Recognition start page=%s fields=%s",self.page+1,sorted(self.target_ids))
        pdf=None
        try:
            pdf=PdfDocument(self.path,textful=self.textful); result={}
            for f in self.fields:
                if f.id not in self.target_ids:continue
                if getattr(f,"default_is_expression",False) and not self.ocr_expression:
                    result[f.id]=[]; continue
                try:
                    raw_options=recognize_field(pdf,self.page,f,self.fields,self.engine,self.ocr_enabled)
                    if f.pattern:
                        hits=[]
                        for raw in raw_options:
                            for hit in find_all(raw,f.pattern):
                                if hit not in hits:hits.append(hit)
                        result[f.id]=hits
                    else:
                        result[f.id]=list(dict.fromkeys(raw.strip() for raw in raw_options if raw.strip()))
                except Exception as exc:
                    LOGGER.exception("OCR field failed id=%s page=%s",f.id,self.page+1)
                    self.completed.emit(self.page,{},f"Field {f.id}: {exc}"); return
                LOGGER.debug("Recognition field=%s hits=%s",f.id,result[f.id])
            LOGGER.info("Recognition done page=%s",self.page+1)
            self.completed.emit(self.page,result,"")
        except Exception as exc:
            LOGGER.exception("OCR recognition failed on page %s",self.page+1)
            self.completed.emit(self.page,{},str(exc))
        finally:
            if pdf:pdf.close()

class HelpWindow(QDialog):
    def __init__(self,parent,cheat=False):
        super().__init__(parent); self.cheat=cheat; self.setModal(False); self.resize(720,600)
        self.browser=QTextBrowser(); lay=QVBoxLayout(self); lay.addWidget(self.browser); self.reload()
    def reload(self):
        code=get_i18n().language; kind="cheatsheet" if self.cheat else "how_to"
        path=resource_path("help",f"{kind}_{code}.html")
        self.browser.setHtml(path.read_text(encoding="utf-8") if path.exists() else str(path)); self.setWindowTitle(t("menu.help.cheatsheet" if self.cheat else "menu.help.howto"))
    def keyPressEvent(self,e):
        if e.key()==Qt.Key.Key_Escape:self.hide()
        else:super().keyPressEvent(e)

class ConfigDialog(QDialog):
    def __init__(self,parent,config):
        super().__init__(parent); self.setWindowTitle(t("dialog.config.title")); self.engine=dict(config["engine"]); self.widgets={}
        lay=QVBoxLayout(self); form=QFormLayout(); lay.addLayout(form)
        for k,(lo,hi) in ENGINE_LIMITS.items():
            w=QDoubleSpinBox() if k in ("drop_score","ocr_contrast") else QSpinBox(); w.setRange(lo,hi); w.setSingleStep(.1) if isinstance(w,QDoubleSpinBox) else None; w.setValue(self.engine[k]); w.setToolTip(t(f"config.{k}.tooltip")+" "+t("tooltip.range",minimum=lo,maximum=hi)); form.addRow(t(f"config.{k}.label"),w); self.widgets[k]=w
        for k in ("use_angle_cls","lang_eslav","lang_latin","lang_chinese","prefer_native_text"):
            w=QCheckBox(); w.setChecked(bool(self.engine[k])); w.setToolTip(t(f"config.{k}.tooltip")); form.addRow(t(f"config.{k}.label"),w); self.widgets[k]=w
        self.logging_enabled=QCheckBox(); self.logging_enabled.setChecked(bool(config.get("logging_enabled",False))); self.log_path=QLineEdit(config.get("log_path", "")); log_browse=QPushButton(t("ui.browse")); log_row=QHBoxLayout(); log_row.addWidget(self.log_path); log_row.addWidget(log_browse); form.addRow(t("config.logging_enabled.label"),self.logging_enabled); form.addRow(t("config.log_path.label"),log_row); self.logging_enabled.setToolTip(t("config.logging_enabled.tooltip")); self.log_path.setToolTip(t("config.log_path.tooltip")); log_browse.clicked.connect(self.choose_log)
        levels=normalize_log_levels(config.get("log_levels")); self.level_checks={}; level_row=QHBoxLayout()
        for name in LOG_LEVEL_NAMES:
            box=QCheckBox(t("config.log_level."+name)); box.setChecked(bool(levels.get(name,True))); box.setToolTip(t("config.log_levels.tooltip")); self.level_checks[name]=box; level_row.addWidget(box)
        form.addRow(t("config.log_levels.label"),level_row)
        self.default_strategy=QComboBox()
        for strategy in OCR_STRATEGIES:self.default_strategy.addItem(t("ocr.strategy."+strategy),strategy)
        self.default_strategy.setCurrentIndex(max(0,self.default_strategy.findData(self.engine.get("default_preprocess_strategy","standard"))))
        self.default_strategy.setToolTip(t("config.default_preprocess_strategy.tooltip")); form.addRow(t("config.default_preprocess_strategy.label"),self.default_strategy)
        self.reset_windows_btn=QPushButton(t("config.reset_windows")); self.reset_windows_btn.setToolTip(t("config.reset_windows.tooltip")); form.addRow(self.reset_windows_btn)
        if isinstance(parent,MainWindow):self.reset_windows_btn.clicked.connect(parent.reset_window_positions)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.RestoreDefaults|QDialogButtonBox.StandardButton.Cancel); lay.addWidget(buttons)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.defaults)
    def defaults(self):
        for k,w in self.widgets.items(): w.setChecked(DEFAULT_ENGINE[k]) if isinstance(w,QCheckBox) else w.setValue(DEFAULT_ENGINE[k])
        self.default_strategy.setCurrentIndex(max(0,self.default_strategy.findData("standard")))
        self.logging_enabled.setChecked(False)
        for name,box in self.level_checks.items():box.setChecked(True)
    def choose_log(self):
        path,_=QFileDialog.getSaveFileName(self,t("config.log_path.label"),self.log_path.text(),"Log (*.log);;All files (*)")
        if path:self.log_path.setText(path)
    def selected_log_levels(self)->dict:
        return {name:box.isChecked() for name,box in self.level_checks.items()}
    def accept(self):
        if not any(self.widgets[k].isChecked() for k in ("lang_eslav","lang_latin","lang_chinese")):
            QMessageBox.warning(self,t("dialog.config.title"),t("error.language_required")); return
        for k,w in self.widgets.items(): self.engine[k]=w.isChecked() if isinstance(w,QCheckBox) else w.value()
        self.engine["ocr_engine"]="rapidocr"
        self.engine["default_preprocess_strategy"]=self.default_strategy.currentData() or "standard"
        if self.logging_enabled.isChecked() and not self.log_path.text().strip():return
        if self.logging_enabled.isChecked() and not any(self.selected_log_levels().values()):
            QMessageBox.warning(self,t("dialog.config.title"),t("error.log_levels_required")); return
        super().accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.config=load_config(); set_language(self.config["ui_language"]); self.pdf=None; self.pdf_path=None; self.fields=[]; self.current_page=0; self.page_status=[]; self.rotations=[]; self.save_index=0; self.page_save_slot={}; self.profile_path=None; self.issued=set(); self.help=None; self.cheat=None; self.worker=None; self.auto_state=None; self.engine_loaders=[]; self.window_pos={}
        self.build_ui(); self.apply_appearance(); self.retranslate(); self.resize(1450,850); self.preload_engine()
    def preload_engine(self):
        name=self.config["engine"].get("ocr_engine","rapidocr"); self.statusBar().showMessage(t("status.engine_loading",engine=t("ocr.engine."+name))); options=dict(self.config["engine"]); options["auto_deskew"]=self.deskew.isChecked() if hasattr(self,"deskew") else bool(options.get("auto_deskew",True)); loader=EngineWarmupWorker(name,options); self.engine_loaders.append(loader)
        def loaded(error):
            if error:
                LOGGER.error("OCR engine preload failed: %s",error); self.statusBar().showMessage(t("status.engine_error",error=error))
            else:
                LOGGER.info("OCR engine ready")
                self.statusBar().showMessage(t("status.ready"))
            if loader in self.engine_loaders:self.engine_loaders.remove(loader)
        loader.completed.connect(loaded,Qt.ConnectionType.QueuedConnection); loader.start()
    def start_recognition(self,worker,slot):
        worker.setParent(self); worker.completed.connect(slot,Qt.ConnectionType.QueuedConnection); self.worker=worker; worker.start()
    def release_worker(self):
        worker=self.worker; self.worker=None
        if worker is None:return
        if worker.isRunning():
            worker.wait(60000)
            if worker.isRunning():
                LOGGER.error("Recognition worker did not stop within 60 seconds; retaining it until process exit")
                worker.setParent(None)
                return
        worker.deleteLater()
    def build_ui(self):
        root=QWidget(); self.setCentralWidget(root); outer=QVBoxLayout(root); top=QFormLayout(); outer.addLayout(top)
        self.top_file_label=QLabel(); self.top_output_label=QLabel(); self.top_template_label=QLabel()
        self.file_edit=QLineEdit(); self.file_edit.setReadOnly(True); self.file_btn=QPushButton(); self.ocr_cb=QCheckBox(); row=QHBoxLayout(); row.addWidget(self.file_edit); row.addWidget(self.file_btn); row.addWidget(self.ocr_cb); top.addRow(self.top_file_label,row)
        self.out_edit=QLineEdit(self.config.get("output_folder","")); self.out_btn=QPushButton(); self.out_relative=QCheckBox(); self.out_relative.setChecked(bool(self.config.get("output_relative",False))); row2=QHBoxLayout(); row2.addWidget(self.out_edit); row2.addWidget(self.out_btn); row2.addWidget(self.out_relative); top.addRow(self.top_output_label,row2)
        self.template=QLineEdit("page_{1}_{1:+1#}"); self.filename=QLineEdit(); self.question=QPushButton("?"); row3=QHBoxLayout(); row3.addWidget(self.template); row3.addWidget(self.question); row3.addWidget(self.filename); top.addRow(self.top_template_label,row3)
        self.load_profile_btn=QPushButton(); self.save_profile_btn=QPushButton(); self.page_format=QComboBox(); self.page_format.addItems(["from_pdf","A3","A4","A5","A6","Letter","Legal","custom"]); self.custom_w=QDoubleSpinBox(); self.custom_h=QDoubleSpinBox(); self.custom_unit=QComboBox(); self.custom_unit.addItems(["mm","cm","in"]); self._custom_unit_prev="mm"
        for w in (self.custom_w,self.custom_h):w.setRange(.1,10000); w.setDecimals(2)
        self.custom_w.setValue(210); self.custom_h.setValue(297); self.custom_w.hide(); self.custom_h.hide(); self.custom_unit.hide()
        self.deskew=QCheckBox(); self.deskew.setChecked(bool(self.config["engine"].get("auto_deskew",True))); self.config_btn=QPushButton(); row4=QHBoxLayout()
        for w in (self.load_profile_btn,self.save_profile_btn,self.page_format,self.custom_w,self.custom_h,self.custom_unit,self.deskew,self.config_btn):row4.addWidget(w)
        outer.addLayout(row4)
        split=QSplitter(); outer.addWidget(split,1); self.pages=QListWidget(); self.pages.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.pages.customContextMenuRequested.connect(self.show_page_menu); split.addWidget(self.pages)
        mid=QWidget(); ml=QVBoxLayout(mid); self.field_header=QLabel(); self.cheat_btn=QPushButton(); hh=QHBoxLayout(); hh.addWidget(self.field_header); hh.addWidget(self.cheat_btn); ml.addLayout(hh); self.field_list=QListWidget(); ml.addWidget(self.field_list); self.add_btn=QPushButton(); self.del_btn=QPushButton(); bb=QHBoxLayout(); bb.addWidget(self.add_btn); bb.addWidget(self.del_btn); ml.addLayout(bb)
        self.editor=QGroupBox(); ef=QFormLayout(self.editor); self.field_label=QLineEdit(); self.pattern=QLineEdit(); self.default_value=QLineEdit(); self.default_expression=QCheckBox(); self.remember_last=QCheckBox(); self.value=QLineEdit(); self.overlap=QComboBox(); self.overlap.addItems(["recognize","clip"]); self.lang_checks={k:QCheckBox() for k in ("eslav","latin","chinese")}
        self.ef_labels={k:QLabel() for k in ("label","pattern","default_value","langs","overlap","value","geometry","contrast")}; langs=QHBoxLayout(); [langs.addWidget(x) for x in self.lang_checks.values()]; ef.addRow(self.ef_labels["label"],self.field_label); ef.addRow(self.ef_labels["pattern"],self.pattern); default_row=QVBoxLayout(); default_row.addWidget(self.default_value); default_modes=QHBoxLayout(); default_modes.addWidget(self.default_expression); default_modes.addWidget(self.remember_last); default_row.addLayout(default_modes); ef.addRow(self.ef_labels["default_value"],default_row); ef.addRow(self.ef_labels["langs"],langs); ef.addRow(self.ef_labels["overlap"],self.overlap)
        geometry=QHBoxLayout(); self.rect_unit=QComboBox(); self.rect_unit.addItems(["%","px","mm","cm"]); self.rect_spins={k:QDoubleSpinBox() for k in ("x","y","w","h")}
        for key,spin in self.rect_spins.items():spin.setRange(0,100000); spin.setDecimals(2); spin.setPrefix(key.upper()+": "); geometry.addWidget(spin)
        geometry.addWidget(self.rect_unit); ef.addRow(self.ef_labels["geometry"],geometry)
        contrast_row=QHBoxLayout(); self.contrast_cb=QCheckBox(); self.field_contrast=QDoubleSpinBox(); self.field_contrast.setRange(1,4); self.field_contrast.setSingleStep(.1); self.field_strategy=QComboBox(); self.fill_strategy_combo(self.field_strategy); contrast_row.addWidget(self.contrast_cb); contrast_row.addWidget(self.field_contrast); contrast_row.addWidget(self.field_strategy); ef.addRow(self.ef_labels["contrast"],contrast_row); ef.addRow(self.ef_labels["value"],self.value); ml.addWidget(self.editor); split.addWidget(mid)
        for w in self.lang_checks.values(): w.toggled.connect(self.edit_field)
        preview_box=QWidget(); preview_layout=QVBoxLayout(preview_box); preview_tools=QHBoxLayout(); self.zoom_out_btn=QPushButton("−"); self.zoom_in_btn=QPushButton("+"); self.fit_btn=QPushButton(); self.save_view_btn=QPushButton(); preview_tools.addStretch(); preview_tools.addWidget(self.zoom_out_btn); preview_tools.addWidget(self.zoom_in_btn); preview_tools.addWidget(self.fit_btn); preview_tools.addWidget(self.save_view_btn); preview_layout.addLayout(preview_tools); self.preview=PreviewView(); preview_layout.addWidget(self.preview,1); split.addWidget(preview_box); split.setSizes([180,360,900])
        bot=QHBoxLayout(); self.rec_btn=QPushButton(); self.manual_btn=QPushButton(); self.save_btn=QPushButton(); self.next_btn=QPushButton(); self.auto_btn=QPushButton(); [bot.addWidget(x) for x in (self.rec_btn,self.manual_btn,self.save_btn,self.next_btn,self.auto_btn)]; outer.addLayout(bot)
        self.file_btn.clicked.connect(self.open_pdf); self.out_btn.clicked.connect(self.choose_output); self.out_relative.toggled.connect(self.persist_output); self.out_edit.editingFinished.connect(self.persist_output); self.pages.currentRowChanged.connect(self.select_page); self.add_btn.clicked.connect(self.add_field); self.del_btn.clicked.connect(self.delete_field); self.preview.rect_drawn.connect(self.finish_field); self.preview.rects_changed.connect(self.sync_rects); self.field_list.currentRowChanged.connect(self.select_field)
        self.field_label.textEdited.connect(self.edit_field); self.pattern.textEdited.connect(self.edit_field); self.default_value.textEdited.connect(self.edit_field); self.default_expression.toggled.connect(lambda checked:self.edit_default_modes("expression",checked)); self.remember_last.toggled.connect(lambda checked:self.edit_default_modes("remember",checked)); self.value.textEdited.connect(self.edit_field); self.overlap.currentIndexChanged.connect(self.edit_field); self.template.textEdited.connect(self.update_filename); self.rec_btn.clicked.connect(self.recognize_page); self.manual_btn.clicked.connect(self.manual_input); self.save_btn.clicked.connect(self.save_page); self.next_btn.clicked.connect(self.skip); self.auto_btn.clicked.connect(self.auto); self.question.clicked.connect(self.show_cheat); self.cheat_btn.clicked.connect(self.show_cheat); self.load_profile_btn.clicked.connect(self.load_profile_file); self.save_profile_btn.clicked.connect(self.save_profile_file); self.config_btn.clicked.connect(self.show_config); self.deskew.toggled.connect(self.persist); self.ocr_cb.toggled.connect(self.persist); self.preview.field_selected.connect(self.select_preview_field); self.page_format.currentTextChanged.connect(self.toggle_custom); self.custom_unit.currentTextChanged.connect(self.convert_custom_unit); self.rect_unit.currentTextChanged.connect(self.populate_rect_controls); self.contrast_cb.toggled.connect(self.edit_field_contrast); self.field_contrast.valueChanged.connect(self.edit_field_contrast); self.field_strategy.currentTextChanged.connect(self.edit_field_contrast); self.zoom_out_btn.clicked.connect(lambda:self.preview.zoom(1/1.2)); self.zoom_in_btn.clicked.connect(lambda:self.preview.zoom(1.2)); self.fit_btn.clicked.connect(self.preview.fit); self.save_view_btn.clicked.connect(self.preview.save_default_view)
        for spin in self.rect_spins.values():spin.valueChanged.connect(self.edit_rect_controls)
        self.install_shortcuts()
        self.make_menus()
    def fill_strategy_combo(self,combo):
        for strategy in OCR_STRATEGIES:combo.addItem(t("ocr.strategy."+strategy),strategy)
    def make_menus(self):
        mb=self.menuBar(); self.menus={k:mb.addMenu("") for k in ("file","profile","edit","view","ocr","help")}; self.actions={}
        def act(menu,key,fn,shortcut=None,check=False):
            a=QAction("",self); a.setCheckable(check); a.triggered.connect(fn); a.setShortcut(shortcut or QKeySequence()); menu.addAction(a); self.actions[key]=a; return a
        act(self.menus["file"],"open",self.open_pdf,"Ctrl+O"); act(self.menus["file"],"save_page",self.save_page,"Ctrl+S"); act(self.menus["file"],"auto",self.auto,"Ctrl+Shift+S"); act(self.menus["file"],"exit",self.close)
        act(self.menus["profile"],"profile_load",self.load_profile_file,"Ctrl+L"); act(self.menus["profile"],"profile_save",self.save_profile_file,"Ctrl+Shift+P")
        act(self.menus["edit"],"add_field",self.add_field,"Ctrl+Insert"); act(self.menus["edit"],"delete_field",self.delete_field,"Delete"); act(self.menus["edit"],"recognize_page",self.recognize_page,"F5"); act(self.menus["edit"],"manual_input",self.manual_input,"F6")
        act(self.menus["edit"],"reset_page",self.reset_current_page,"Ctrl+Backspace")
        act(self.menus["view"],"zoom_in",lambda:self.preview.zoom(1.2),"Ctrl++"); act(self.menus["view"],"zoom_out",lambda:self.preview.zoom(1/1.2),"Ctrl+-"); act(self.menus["view"],"fit",self.preview.fit,"Ctrl+0")
        lang=self.menus["view"].addMenu(""); self.lang_menu=lang
        for code in ("ru","en"): a=lang.addAction(code); a.triggered.connect(lambda _=False,c=code:self.change_language(c))
        skin=self.menus["view"].addMenu(""); self.skin_menu=skin
        for x in load_catalog()["skins"]: a=skin.addAction(x["id"]); a.triggered.connect(lambda _=False,c=x["id"]:self.change_skin(c))
        icon=self.menus["view"].addMenu(""); self.icon_menu=icon
        for x in load_catalog()["icons"]: a=icon.addAction(x["id"]); a.triggered.connect(lambda _=False,c=x["id"]:self.change_icon(c))
        act(self.menus["ocr"],"config",self.show_config); act(self.menus["help"],"howto",self.show_help,"F1"); act(self.menus["help"],"cheatsheet",self.show_cheat,"F2"); act(self.menus["help"],"about",self.about)
    def install_shortcuts(self):
        bindings={"Ctrl+Right":self.skip,"Alt+L":self.field_label.setFocus,"Alt+P":self.pattern.setFocus,"Alt+V":self.value.setFocus,"Alt+G":self.rect_spins["x"].setFocus,"Alt+C":self.field_contrast.setFocus,"Ctrl+Comma":self.show_config}
        self.shortcuts=[]
        for sequence,callback in bindings.items():shortcut=QShortcut(QKeySequence(sequence),self); shortcut.activated.connect(callback); self.shortcuts.append(shortcut)
        order=[self.field_label,self.pattern,self.default_value,self.default_expression,self.remember_last,self.lang_checks["eslav"],self.lang_checks["latin"],self.lang_checks["chinese"],self.overlap,self.rect_spins["x"],self.rect_spins["y"],self.rect_spins["w"],self.rect_spins["h"],self.rect_unit,self.contrast_cb,self.field_contrast,self.field_strategy,self.value]
        for first,second in zip(order,order[1:]):self.setTabOrder(first,second)
    def retranslate(self):
        self.setWindowTitle(t("app.name"));
        for k,m in self.menus.items():m.setTitle(t("menu."+k))
        mapping={"open":"menu.file.open","save_page":"menu.file.save_page","auto":"menu.file.auto","exit":"menu.file.exit","profile_load":"menu.profile.load","profile_save":"menu.profile.save","add_field":"menu.edit.add_field","delete_field":"menu.edit.delete_field","recognize_page":"menu.edit.recognize_page","manual_input":"menu.edit.manual_input","reset_page":"menu.edit.reset_page","zoom_in":"menu.view.zoom_in","zoom_out":"menu.view.zoom_out","fit":"menu.view.fit","config":"menu.ocr.config","howto":"menu.help.howto","cheatsheet":"menu.help.cheatsheet","about":"menu.help.about"}
        for k,v in mapping.items():self.actions[k].setText(t(v))
        self.lang_menu.setTitle(t("menu.view.language")); self.skin_menu.setTitle(t("menu.view.skin")); self.icon_menu.setTitle(t("menu.view.icon"))
        for w,key in ((self.file_btn,"ui.browse"),(self.out_btn,"ui.browse"),(self.load_profile_btn,"ui.load_profile"),(self.save_profile_btn,"ui.save_profile"),(self.deskew,"ui.deskew"),(self.config_btn,"ui.config"),(self.field_header,"ui.fields"),(self.cheat_btn,"ui.cheatsheet"),(self.add_btn,"ui.add_field"),(self.del_btn,"ui.delete_field"),(self.rec_btn,"ui.recognize_page"),(self.manual_btn,"ui.manual_input"),(self.save_btn,"ui.save"),(self.next_btn,"ui.next"),(self.auto_btn,"ui.auto"),(self.ocr_cb,"ui.ocr"),(self.out_relative,"ui.output_relative")):w.setText(t(key))
        self.auto_btn.setToolTip(t("ui.auto.tooltip")+" (Ctrl+Shift+S)"); self.rec_btn.setToolTip(t("tooltip.hotkey",shortcut="F5")); self.manual_btn.setToolTip(t("tooltip.manual_input")+" "+t("tooltip.hotkey",shortcut="F6")); self.save_btn.setToolTip(t("tooltip.hotkey",shortcut="Ctrl+S")); self.next_btn.setToolTip(t("tooltip.hotkey",shortcut="Ctrl+Right")); self.add_btn.setToolTip(t("tooltip.hotkey",shortcut="Ctrl+Insert")); self.del_btn.setToolTip(t("tooltip.hotkey",shortcut="Delete")); self.out_relative.setToolTip(t("tooltip.output_relative")); self.statusBar().showMessage(t("status.ready"));
        self.top_file_label.setText(t("ui.file")); self.top_output_label.setText(t("ui.output_folder")); self.top_template_label.setText(t("ui.name_template"))
        for key,label in self.ef_labels.items():label.setText(t("ui."+("field_label" if key=="label" else key if key!="langs" else "ocr_languages")))
        self.contrast_cb.setText(t("ui.contrast.enable"))
        self.default_expression.setText(t("ui.default_expression")); self.remember_last.setText(t("ui.remember_last")); self.fit_btn.setText(t("ui.fit")); self.save_view_btn.setText(t("ui.save_view")); self.zoom_in_btn.setToolTip(t("menu.view.zoom_in")+" (Ctrl++)"); self.zoom_out_btn.setToolTip(t("menu.view.zoom_out")+" (Ctrl+-)"); self.fit_btn.setToolTip(t("menu.view.fit")+" (Ctrl+0)"); self.save_view_btn.setToolTip(t("tooltip.save_view"))
        self.lang_checks["eslav"].setText(t("ocr.lang.cyrillic")); self.lang_checks["latin"].setText(t("ocr.lang.latin")); self.lang_checks["chinese"].setText(t("ocr.lang.chinese"))
        for index in range(self.field_strategy.count()):self.field_strategy.setItemText(index,t("ocr.strategy."+self.field_strategy.itemData(index)))
        tips={self.field_label:"tooltip.field.label",self.pattern:"tooltip.field.pattern",self.default_value:"tooltip.field.default_value",self.default_expression:"tooltip.field.default_expression",self.remember_last:"tooltip.field.remember_last",self.value:"tooltip.field.value",self.overlap:"ui.overlap.tooltip",self.template:"tooltip.name_template",self.filename:"tooltip.filename",self.page_format:"tooltip.page_format",self.custom_w:"tooltip.custom_size",self.custom_h:"tooltip.custom_size"}
        for widget,key in tips.items():widget.setToolTip(t(key))
        for key,widget in self.lang_checks.items():widget.setToolTip(t("tooltip.ocr_language"))
        self.field_contrast.setToolTip(t("tooltip.field.contrast")+" "+t("tooltip.range",minimum=1,maximum=4)); self.contrast_cb.setToolTip(t("tooltip.field.contrast")); self.field_strategy.setToolTip(t("tooltip.field.strategy")); self.rect_unit.setToolTip(t("tooltip.field.geometry"))
        for widget in self.rect_spins.values():widget.setToolTip(t("tooltip.field.geometry"))
        if self.help:self.help.reload()
        if self.cheat:self.cheat.reload()
    def apply_appearance(self):
        QApplication.instance().setStyleSheet(qss_for_skin(skin_by_id(self.config["ui_skin"]))); self.setWindowIcon(QIcon(str(icon_path(self.config["ui_icon"]))))
    def persist(self):
        self.config["engine"]["auto_deskew"]=self.deskew.isChecked(); self.persist_output(save=False); save_config(self.config)
    def persist_output(self,save=True):
        self.config["output_folder"]=self.out_edit.text().strip(); self.config["output_relative"]=self.out_relative.isChecked()
        if save:save_config(self.config)
    def output_base_dir(self)->Path|None:
        if self.pdf_path:return self.pdf_path.parent
        if self.profile_path:return self.profile_path.parent
        return Path.cwd()
    def resolved_output_dir(self)->Path:
        return resolve_output_dir(self.out_edit.text(),relative=self.out_relative.isChecked(),base=self.output_base_dir())
    def ensure_output_dir(self,folder:Path)->bool:
        if not str(folder):return False
        if folder.exists():
            if folder.is_dir():return True
            self.fail(t("error.output_not_dir",path=str(folder))); return False
        answer=QMessageBox.question(self,t("dialog.create_folder.title"),t("dialog.create_folder.body",path=str(folder)),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes:return False
        try:
            folder.mkdir(parents=True,exist_ok=True); return True
        except OSError:
            LOGGER.exception("Cannot create output folder %s",folder); self.fail(t("error.create_folder",path=str(folder))); return False
    def choose_output(self):
        start=str(self.resolved_output_dir() or self.output_base_dir() or "")
        p=QFileDialog.getExistingDirectory(self,t("menu.file.output_folder"),start)
        if not p:return
        chosen=Path(p); base=self.output_base_dir()
        if self.out_relative.isChecked() and base is not None:
            try:self.out_edit.setText(str(chosen.resolve().relative_to(base.resolve())))
            except ValueError:self.out_edit.setText(str(chosen)); self.out_relative.setChecked(False)
        else:self.out_edit.setText(str(chosen))
        self.persist_output()
    def change_language(self,c): self.config["ui_language"]=c; set_language(c); self.retranslate(); self.persist()
    def change_skin(self,c):
        self.config["ui_skin"]=c
        if not self.config["ui_icon_locked"]:self.config["ui_icon"]=default_icon_for_skin(c)
        self.apply_appearance(); self.persist()
    def change_icon(self,c):self.config["ui_icon"]=c; self.config["ui_icon_locked"]=True; self.apply_appearance(); self.persist()
    def open_pdf(self):
        p,_=QFileDialog.getOpenFileName(self,t("menu.file.open"),"","PDF (*.pdf)")
        if not p:return
        candidate=None
        try:
            LOGGER.info("Opening PDF %s",p)
            candidate=PdfDocument(Path(p)); old=self.pdf; self.pdf=candidate; candidate=None
            if old:old.close()
            self.pdf_path=Path(p); self.file_edit.setText(p); self.current_page=0; self.page_status=["pending"]*len(self.pdf.doc); self.rotations=[0]*len(self.pdf.doc); self.save_index=0; self.page_save_slot={}; self.issued=set(); self.fields=[]; self.profile_path=None; self.pages.clear(); self.preview.reset_view()
            for i in range(len(self.pdf.doc)):self.pages.addItem(f"{i+1} — {t('page.pending')}")
            self.ocr_cb.setChecked(self.pdf.kind!="digital"); self.pages.setCurrentRow(0); self.statusBar().showMessage(t("status."+self.pdf.kind))
            self.refresh_pages()
            LOGGER.info("Opened PDF pages=%s kind=%s",len(self.pdf.doc),self.pdf.kind)
        except PermissionError:
            if candidate:candidate.close()
            LOGGER.warning("Encrypted PDF %s",p); QMessageBox.critical(self,t("app.name"),t("error.encrypted"))
        except Exception:
            if candidate:
                try:candidate.close()
                except Exception:pass
            LOGGER.exception("Failed to open PDF %s",p); self.fail(t("error.bad_pdf"))
    def select_page(self,i):
        if i<0 or not self.pdf:return
        LOGGER.debug("Select page %s",i+1)
        self.sync_rects(); self.current_page=i
        try:
            pix=self.pdf.render(i,110,self.rotations[i]); self.preview.set_pixmap_data(pix.samples,pix.width,pix.height,pix.stride); self.preview.set_fields(self.fields); self.refresh_field_list(); self.update_filename(); self.statusBar().showMessage(t("status.page_of",current=i+1,total=len(self.pdf.doc)))
        except Exception:
            LOGGER.exception("Render failed on page %s",i+1); self.fail(t("error.render"))
    def refresh_pages(self):
        for i,s in enumerate(self.page_status):self.pages.item(i).setText(f"{i+1} — {t('page.'+s)}")
    def add_field(self):
        if not self.pdf:return
        self.preview.start_drawing(); self.statusBar().showMessage(t("status.draw_field"))
    def finish_field(self,rect):
        strategy=str(self.config["engine"].get("default_preprocess_strategy") or "standard")
        self.fields.append(Field(len(self.fields)+1,rect=rect,preprocess_strategy=valid_preprocess_strategy(strategy))); self.preview.set_fields(self.fields); self.refresh_field_list(); self.field_list.setCurrentRow(len(self.fields)-1)
    def delete_field(self):
        i=self.field_list.currentRow()
        if i<0:return
        self.fields.pop(i)
        for n,f in enumerate(self.fields,1):f.id=n
        self.preview.set_fields(self.fields); self.refresh_field_list(); QMessageBox.warning(self,t("app.name"),t("warn.fields_renumbered")); self.update_filename()
    def sync_rects(self):
        rects=self.preview.normalized_rects()
        for f in self.fields:
            if f.id in rects:f.rect=rects[f.id]
        self.populate_rect_controls()
    def refresh_field_list(self):
        old=self.field_list.currentRow(); self.field_list.blockSignals(True); self.field_list.clear()
        for f in self.fields:self.field_list.addItem(f"{f.id}. {f.label or t('ui.field_label')} — {f.statuses.get(self.current_page,'empty')}")
        self.field_list.blockSignals(False); self.field_list.setCurrentRow(min(old,len(self.fields)-1))
    def select_field(self,i):
        if i<0 or i>=len(self.fields):return
        f=self.fields[i]
        self.preview.select_field(f.id)
        for w in (self.field_label,self.pattern,self.default_value,self.default_expression,self.remember_last,self.value,self.overlap):w.blockSignals(True)
        self.field_label.setText(f.label); self.pattern.setText(f.pattern); self.default_value.setText(f.default_value); self.default_expression.setChecked(f.default_is_expression); self.remember_last.setChecked(f.remember_last_value); self.value.setText(f.value(self.current_page)); self.overlap.setCurrentText(f.overlap_mode)
        for k,w in self.lang_checks.items():w.setChecked(k in f.ocr_langs); w.setEnabled(bool(self.config["engine"].get("lang_"+k)))
        for w in (self.field_label,self.pattern,self.default_value,self.default_expression,self.remember_last,self.value,self.overlap):w.blockSignals(False)
        self.contrast_cb.blockSignals(True); self.field_contrast.blockSignals(True); self.field_strategy.blockSignals(True); self.contrast_cb.setChecked(f.contrast>1.01); self.field_contrast.setValue(max(1,f.contrast)); self.field_contrast.setEnabled(self.contrast_cb.isChecked()); self.field_strategy.setCurrentIndex(max(0,self.field_strategy.findData(f.preprocess_strategy))); self.field_strategy.setEnabled(True); self.contrast_cb.blockSignals(False); self.field_contrast.blockSignals(False); self.field_strategy.blockSignals(False); self.populate_rect_controls()
    def select_preview_field(self,field_id):
        row=field_id-1
        if 0<=row<len(self.fields) and self.field_list.currentRow()!=row:self.field_list.setCurrentRow(row)
    def _page_metrics(self):
        if not self.pdf:return 1.0,1.0,1.0,1.0
        page=self.pdf.doc[self.current_page]; mm_w=page.rect.width*25.4/72; mm_h=page.rect.height*25.4/72; scene=self.preview.sceneRect(); return scene.width() or 1,scene.height() or 1,mm_w,mm_h
    def populate_rect_controls(self,*_):
        i=self.field_list.currentRow()
        if i<0 or i>=len(self.fields):return
        r=self.fields[i].rect; pw,ph,mw,mh=self._page_metrics(); unit=self.rect_unit.currentText(); factors={"%":(100,100),"px":(pw,ph),"mm":(mw,mh),"cm":(mw/10,mh/10)}; fx,fy=factors[unit]
        values={"x":r["x"]*fx,"y":r["y"]*fy,"w":r["w"]*fx,"h":r["h"]*fy}
        for key,spin in self.rect_spins.items():spin.blockSignals(True); spin.setValue(values[key]); spin.blockSignals(False)
    def edit_rect_controls(self,*_):
        i=self.field_list.currentRow()
        if i<0 or i>=len(self.fields):return
        pw,ph,mw,mh=self._page_metrics(); unit=self.rect_unit.currentText(); factors={"%":(100,100),"px":(pw,ph),"mm":(mw,mh),"cm":(mw/10,mh/10)}; fx,fy=factors[unit]
        r={"x":self.rect_spins["x"].value()/fx,"y":self.rect_spins["y"].value()/fy,"w":self.rect_spins["w"].value()/fx,"h":self.rect_spins["h"].value()/fy}
        r["x"]=max(0,min(1,r["x"])); r["y"]=max(0,min(1,r["y"])); r["w"]=max(.001,min(1-r["x"],r["w"])); r["h"]=max(.001,min(1-r["y"],r["h"])); self.fields[i].rect=r; self.preview.set_fields(self.fields); self.preview.select_field(self.fields[i].id)
    def edit_field_contrast(self,*_):
        i=self.field_list.currentRow()
        if i<0 or i>=len(self.fields):return
        self.field_contrast.setEnabled(self.contrast_cb.isChecked()); self.field_strategy.setEnabled(True); self.fields[i].contrast=self.field_contrast.value() if self.contrast_cb.isChecked() else 1.0; self.fields[i].preprocess_strategy=self.field_strategy.currentData() or "standard"
    def toggle_custom(self,value):
        visible=value=="custom"
        for widget in (self.custom_w,self.custom_h,self.custom_unit):widget.setVisible(visible)
    def convert_custom_unit(self,new_unit):
        old=self._custom_unit_prev
        if new_unit==old:return
        for widget in (self.custom_w,self.custom_h):widget.setValue(convert_page_value(widget.value(),old,new_unit))
        self._custom_unit_prev=new_unit
    def custom_mm(self):
        factor=PAGE_UNIT_MM[self.custom_unit.currentText()]
        return self.custom_w.value()*factor,self.custom_h.value()*factor
    def edit_field(self,*_):
        i=self.field_list.currentRow()
        if i<0:return
        f=self.fields[i]; f.label=self.field_label.text(); f.pattern=self.pattern.text(); f.default_value=self.default_value.text(); f.overlap_mode=self.overlap.currentText(); f.values[self.current_page]=self.value.text(); f.statuses[self.current_page]="manual"; f.ocr_langs=[k for k,w in self.lang_checks.items() if w.isChecked()]; self.refresh_field_list(); self.update_filename()
    def edit_default_modes(self,mode,checked):
        i=self.field_list.currentRow()
        if i<0:return
        f=self.fields[i]
        if mode=="expression":
            f.default_is_expression=checked
            if checked:
                self.remember_last.blockSignals(True); self.remember_last.setChecked(False); self.remember_last.blockSignals(False); f.remember_last_value=False
                if not f.default_value.strip() and is_counter_template(f.pattern):
                    f.default_value=f.pattern.strip(); self.default_value.blockSignals(True); self.default_value.setText(f.default_value); self.default_value.blockSignals(False)
                issue=expression_issue(f.default_value.strip() or (f.pattern.strip() if is_counter_template(f.pattern) else ""))
                if issue:
                    QMessageBox.warning(self,t("app.name"),t("warn.expression."+issue,id=f.id,pattern=f.pattern or f.default_value))
                    self.default_expression.blockSignals(True); self.default_expression.setChecked(False); self.default_expression.blockSignals(False)
                    f.default_is_expression=False; return
            if checked and self.current_page>=0:
                value=self.effective_default(f,self.current_page)
                if value:
                    f.values[self.current_page]=value; f.statuses[self.current_page]="ok"; self.value.blockSignals(True); self.value.setText(value); self.value.blockSignals(False)
            self.refresh_field_list(); self.update_filename()
        else:
            f.remember_last_value=checked
            if checked:self.default_expression.blockSignals(True); self.default_expression.setChecked(False); self.default_expression.blockSignals(False); f.default_is_expression=False
    def effective_default(self,f,page):
        if not f.default_is_expression:return f.default_value
        slot=self.page_save_slot.get(page,self.save_index)
        template=f.default_value.strip() or (f.pattern.strip() if is_counter_template(f.pattern) else "")
        return expand_template_safe(template,{},page,slot)
    def page_filename(self,page):
        vals={f.id:f.value(page) for f in self.fields}; slot=self.page_save_slot.get(page,self.save_index)
        try:return build_filename(self.template.text(),vals,page,slot)
        except Exception:
            LOGGER.exception("Filename expand failed page=%s",page+1); return f"page_{page+1}.pdf"
    def warn_field_input(self):
        lines=[]
        for f in self.fields:
            if f.default_is_expression:
                issue=expression_issue(f.default_value.strip() or (f.pattern.strip() if is_counter_template(f.pattern) else ""))
                if issue:lines.append(t("warn.expression."+issue,id=f.id,pattern=f.pattern or f.default_value))
            elif f.pattern:
                issue=pattern_issue(f.pattern)
                if issue:lines.append(t("warn.pattern."+issue,id=f.id,pattern=f.pattern))
        if lines:QMessageBox.warning(self,t("app.name"),"\n".join(lines))
        return True
    def update_filename(self):
        self.filename.setText(self.page_filename(self.current_page))
    def recognize_page(self,auto=False):
        if not self.pdf:return False
        if self.auto_state or (self.worker and self.worker.isRunning()):
            LOGGER.info("Recognize ignored: OCR busy"); self.statusBar().showMessage(t("status.ocr_busy")); return False
        self.warn_field_input()
        for f in self.fields:
            if not f.pattern and not f.default_is_expression and not auto:
                answer=QMessageBox.question(self,t("ui.pattern"),t("dialog.empty_pattern.body"),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel)
                if answer==QMessageBox.StandardButton.Cancel:return False
        page=self.current_page; LOGGER.info("Manual recognize page=%s",page+1); self.statusBar().showMessage(t("status.recognizing",page=page+1)); engine=dict(self.config["engine"]); engine["auto_deskew"]=self.deskew.isChecked(); self.start_recognition(RecognitionWorker(self.pdf_path,page,self.fields,engine,self.ocr_cb.isChecked(),textful=self.pdf.textful),lambda p,r,e:self.finish_manual_recognition(p,r,e,auto))
        return True
    def apply_recognition_result(self,page,results,choose=False):
        for f in self.fields:
            if f.default_is_expression:
                f.values[page]=self.effective_default(f,page); f.statuses[page]="ok" if f.values[page].strip() else "empty"; f.candidates[page]=[]; continue
            hits=list(results.get(f.id,[]) or [])
            f.candidates[page]=[text for text in hits if str(text).strip()]
            if len(hits)>1 and choose:
                chosen=self.choose_candidate(hits,f); hits=[chosen] if chosen else []
            f.values[page]=hits[0] if hits else self.effective_default(f,page); f.statuses[page]="ambiguous" if len(hits)>1 else ("ok" if hits else "empty")
        self.page_status[page]="recognized"; self.refresh_pages()
        if self.current_page==page:self.refresh_field_list(); self.update_filename()
    def finish_manual_recognition(self,page,results,error,auto=False):
        self.release_worker()
        if error:
            LOGGER.error("OCR failed on page %s: %s",page+1,error)
            self.page_status[page]="error"; self.refresh_pages(); QMessageBox.warning(self,t("app.name"),t("error.ocr",error=error)); return
        self.apply_recognition_result(page,results,choose=not auto)
        if not auto:
            self.pages.setCurrentRow(page); missing=empty_fields(self.fields,page)
            if missing:self.resolve_auto_page(missing,manual=True)
        self.statusBar().showMessage(t("status.ready"))
    def manual_input(self):
        if not self.pdf or not self.fields:return
        decision=self.resolve_auto_page([],manual=True)
        if decision=="apply":self.save_page()
        elif decision=="skip":self.skip()
    def fill_choice_combo(self,combo,hits,default,current=""):
        combo.blockSignals(True); combo.clear()
        for source,value in field_choice_items(hits,default):
            combo.addItem(t("dialog.candidates."+source)+": "+value,value)
        combo.setCurrentIndex(-1); combo.setEditText(current or default or ""); combo.blockSignals(False)
    def apply_choice_combo_item(self,combo,index):
        data=combo.itemData(index)
        if data is not None:combo.setEditText(str(data))
    def combo_choice_value(self,combo):
        data=combo.currentData()
        if data is not None and combo.currentText()==combo.itemText(combo.currentIndex()):return str(data)
        return combo.currentText()
    def choose_candidate(self,hits,field=None):
        dialog=QDialog(self); dialog.setWindowTitle(t("dialog.candidates.title")); layout=QVBoxLayout(dialog); layout.addWidget(QLabel(t("dialog.candidates.choose"))); choices=QComboBox()
        default=self.effective_default(field,self.current_page) if field else ""
        for source,value in field_choice_items(hits,default):
            choices.addItem(t("dialog.candidates."+source)+": "+value,value)
        layout.addWidget(choices); buttons=QHBoxLayout(); apply_btn=QPushButton(t("dialog.candidates.apply")); manual_btn=QPushButton(t("dialog.candidates.manual")); cancel_btn=QPushButton(t("dialog.manual.cancel")); buttons.addWidget(apply_btn); buttons.addWidget(manual_btn); buttons.addWidget(cancel_btn); layout.addLayout(buttons); result={"value":None}
        def selected_value():
            data=choices.currentData()
            return str(data) if data is not None else choices.currentText()
        def apply_choice():result["value"]=selected_value(); dialog.accept()
        def manual():
            value,ok=__import__('PySide6.QtWidgets',fromlist=['QInputDialog']).QInputDialog.getText(dialog,t("dialog.candidates.manual"),t("ui.value"),text=selected_value() or default)
            if ok:result["value"]=value; dialog.accept()
        apply_btn.clicked.connect(apply_choice); manual_btn.clicked.connect(manual); cancel_btn.clicked.connect(dialog.reject); apply_btn.setDefault(True); escape_shortcut=QShortcut(QKeySequence(Qt.Key.Key_Escape),dialog); escape_shortcut.activated.connect(cancel_btn.click); self.exec_session_dialog("candidates",dialog,modal=False); return result["value"]
    def target_path(self,auto=False,page=None):
        page=self.current_page if page is None else page
        if not self.out_edit.text().strip():self.choose_output()
        if not self.out_edit.text().strip():return None,False
        folder=self.resolved_output_dir()
        if not self.ensure_output_dir(folder):return None,False
        name=self.filename.text() if (not auto and page==self.current_page) else self.page_filename(page)
        base=folder/name; suffixed=False
        if base.exists() or base in self.issued:
            if not auto:
                box=QMessageBox(self); box.setWindowTitle(t("dialog.duplicate.title")); box.setText(t("dialog.duplicate.body",name=base.name)); suffix=box.addButton(t("dialog.duplicate.suffix"),QMessageBox.ButtonRole.AcceptRole); rename=box.addButton(t("dialog.duplicate.rename"),QMessageBox.ButtonRole.ActionRole); box.addButton(QMessageBox.StandardButton.Cancel); box.exec()
                if box.clickedButton()==rename:
                    name,ok=__import__('PySide6.QtWidgets',fromlist=['QInputDialog']).QInputDialog.getText(self,t("dialog.duplicate.title"),t("ui.name_preview"),text=base.stem)
                    if not ok:return None,False
                    base=base.with_name(sanitize_filename(name,page+1)+".pdf")
                    if base.exists() or base in self.issued:return None,False
                elif box.clickedButton()!=suffix:return None,False
            if auto or box.clickedButton()==suffix:
                n=1; stem=base.stem
                while base.exists() or base in self.issued:base=base.with_name(f"{stem}-{n}.pdf"); n+=1
                suffixed=True
        return base,suffixed
    def save_page(self,auto=False,page=None):
        if not self.pdf:return (False,False)
        if self.auto_state and not auto:
            self.statusBar().showMessage(t("status.ocr_busy")); return (False,False)
        page=self.current_page if page is None else page
        if not auto:
            missing=empty_fields(self.fields,page)
            if missing and self.resolve_auto_page(missing,manual=True,page=page)!="apply":return (False,False)
        path,suffix=self.target_path(auto,page)
        if not path:return (False,False)
        try:
            LOGGER.info("Saving page=%s path=%s auto=%s",page+1,path,auto)
            self.pdf.save_page(page,path,self.rotations[page]); self.issued.add(path)
            for f in self.fields:remember_applied_value(f,f.value(page))
            if not auto:
                row=self.field_list.currentRow()
                if row>=0:self.select_field(row)
            if page not in self.page_save_slot:self.page_save_slot[page]=self.save_index; self.save_index+=1
            self.page_status[page]="saved"; self.refresh_pages(); return (True,suffix)
        except Exception:
            LOGGER.exception("Save failed page=%s path=%s",page+1,path); self.fail(t("error.save")); return (False,False)
    def skip(self):
        if not self.pdf or self.auto_state:return
        self.page_status[self.current_page]="skipped"; self.refresh_pages(); self.pages.setCurrentRow(min(self.current_page+1,len(self.page_status)-1))
    def reset_current_page(self):
        if not self.pdf:return
        for f in self.fields:f.values.pop(self.current_page,None); f.statuses.pop(self.current_page,None); f.candidates.pop(self.current_page,None)
        self.page_status[self.current_page]="pending"; self.refresh_pages(); self.refresh_field_list(); self.update_filename()
    def show_page_menu(self,pos):
        item=self.pages.itemAt(pos)
        if not item:return
        self.pages.setCurrentItem(item); menu=QMenu(self); menu.addAction(t("menu.edit.reset_page"),self.reset_current_page); menu.exec(self.pages.mapToGlobal(pos))
    def set_batch_busy(self,busy):
        for widget in (self.rec_btn,self.manual_btn,self.save_btn,self.next_btn,self.auto_btn,self.add_btn,self.del_btn,self.file_btn,self.load_profile_btn,self.save_profile_btn):
            widget.setEnabled(not busy)
        for key in ("open","save_page","auto","add_field","delete_field","recognize_page","manual_input","reset_page"):
            if key in self.actions:self.actions[key].setEnabled(not busy)
        LOGGER.debug("Batch controls busy=%s",busy)
    def mark_auto_page(self,page):
        item=self.pages.item(page)
        if item:self.pages.scrollToItem(item)
    def auto(self):
        if not self.pdf:return
        if self.auto_state or (self.worker and self.worker.isRunning()):LOGGER.info("Auto ignored: OCR busy"); self.statusBar().showMessage(t("status.ocr_busy")); return
        self.warn_field_input()
        empty_patterns=[str(f.id) for f in self.fields if not f.pattern and not f.default_is_expression]
        if empty_patterns and QMessageBox.question(self,t("ui.auto"),t("dialog.empty_pattern.auto"))!=QMessageBox.StandardButton.Yes:return
        LOGGER.info("Auto start pages=%s",len(self.page_status))
        progress=QProgressDialog(t("ui.auto.tooltip"),t("common.cancel"),0,len(self.page_status)); progress.setWindowModality(Qt.WindowModality.NonModal); progress.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,True); progress.setAutoClose(False); progress.setAutoReset(False); progress.setMinimumDuration(0); progress.setWindowTitle(t("ui.auto")); self.show_session_widget("auto_progress",progress)
        self.set_batch_busy(True); self.auto_state={"index":0,"saved":0,"suffix":[],"errors":[],"progress":progress,"cancelled":False}; progress.canceled.connect(self.cancel_auto); self.auto_next()
    def cancel_auto(self):
        LOGGER.warning("Auto cancel requested")
        if self.auto_state:self.auto_state["cancelled"]=True
    def auto_next(self):
        state=self.auto_state
        if not state:return
        while state["index"]<len(self.page_status) and auto_page_plan(self.page_status[state["index"]])=="skip":
            state["progress"].setValue(state["index"]+1); state["index"]+=1
        if state["cancelled"] or state["index"]>=len(self.page_status):self.finish_auto(); return
        i=state["index"]; plan=auto_page_plan(self.page_status[i]); self.mark_auto_page(i); state["progress"].setLabelText(t("status.recognizing",page=i+1)); LOGGER.info("Auto page=%s plan=%s",i+1,plan)
        if plan=="reuse":self.auto_page_ready(i); return
        self.statusBar().showMessage(t("status.recognizing",page=i+1)+" — "+t("status.preview_free")); engine=dict(self.config["engine"]); engine["auto_deskew"]=self.deskew.isChecked(); self.start_recognition(RecognitionWorker(self.pdf_path,i,self.fields,engine,self.ocr_cb.isChecked(),textful=self.pdf.textful),self.finish_auto_recognition)
    def finish_auto_recognition(self,page,results,error):
        self.release_worker()
        if not self.auto_state:return
        if error:
            LOGGER.error("Auto OCR failed on page %s: %s",page+1,error); self.page_status[page]="error"; self.auto_state["errors"].append(str(page+1)); self.refresh_pages()
            self.auto_state["progress"].setValue(page+1); self.auto_state["index"]=page+1; self.auto_next(); return
        else:
            try:self.apply_recognition_result(page,results)
            except Exception:
                LOGGER.exception("Applying OCR result failed page=%s",page+1); self.page_status[page]="error"; self.auto_state["errors"].append(str(page+1)); self.refresh_pages()
                self.auto_state["progress"].setValue(page+1); self.auto_state["index"]=page+1; self.auto_next(); return
        if self.auto_state["cancelled"]:self.finish_auto(); return
        self.auto_page_ready(page)
    def auto_page_ready(self,page):
        state=self.auto_state
        if not state:return
        missing=empty_fields(self.fields,page)
        if missing:
            LOGGER.warning("Auto paused for review page=%s missing=%s",page+1,[f.id for f in missing]); self.hide_session_widget("auto_progress",state["progress"]); self.pages.setCurrentRow(page); decision=self.resolve_auto_page(missing,page=page); self.show_session_widget("auto_progress",state["progress"])
            if decision=="cancel":state["cancelled"]=True; self.finish_auto(); return
            if decision=="skip":self.page_status[page]="skipped"; self.refresh_pages(); state["progress"].setValue(page+1); state["index"]=page+1; self.auto_next(); return
        ok,suf=self.save_page(True,page)
        if ok:state["saved"]+=1
        else:state["errors"].append(str(page+1))
        if suf:state["suffix"].append(str(page+1))
        state["progress"].setValue(page+1); state["index"]=page+1; self.auto_next()
    def finish_auto(self):
        state=self.auto_state
        if not state:return
        LOGGER.info("Auto finished saved=%s errors=%s suffix=%s",state["saved"],state["errors"],state["suffix"])
        self.close_session_widget("auto_progress",state["progress"]); text=t("dialog.auto_report.saved",n=state["saved"])+"\n"+t("dialog.auto_report.suffix")+": "+(", ".join(state["suffix"]) or "—")
        if state["errors"]:text+="\n"+t("dialog.auto_report.errors")+": "+", ".join(state["errors"])
        self.auto_state=None; self.set_batch_busy(False); self.statusBar().showMessage(t("status.ready")); QMessageBox.information(self,t("dialog.auto_report.title"),text)
    def resolve_auto_page(self,missing,manual=False,page=None):
        page=self.current_page if page is None else page
        if page!=self.current_page:self.pages.setCurrentRow(page)
        LOGGER.info("Review dialog page=%s manual=%s missing=%s",page+1,manual,[f.id for f in missing])
        dialog=QDialog(self); dialog.setWindowTitle(t("dialog.recognition_review.title" if manual else "dialog.auto_empty.title")); layout=QVBoxLayout(dialog)
        layout.addWidget(QLabel(t("dialog.auto_empty.body",page=page+1)))
        form=QFormLayout(); layout.addLayout(form); template_edit=QLineEdit(self.template.text()); filename_edit=QLineEdit(self.page_filename(page)); form.addRow(t("ui.name_template"),template_edit); edits={}; contrast_edits={}; strategy_edits={}; retry_workers=[]
        missing_ids={f.id for f in missing}
        for f in self.fields:
            default=self.effective_default(f,page); current=f.value(page) or default
            edit=QComboBox(); edit.setEditable(True); edit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert); edit.setToolTip(t("dialog.recognition_review.value.tooltip")); self.fill_choice_combo(edit,f.candidates.get(page,[]),default,current); edits[f.id]=edit; contrast=QDoubleSpinBox(); contrast.setRange(1,4); contrast.setSingleStep(.1); contrast.setValue(f.contrast); contrast.setToolTip(t("tooltip.field.contrast")+" "+t("tooltip.range",minimum=1,maximum=4)); contrast_edits[f.id]=contrast; strategy=QComboBox(); self.fill_strategy_combo(strategy); strategy.setCurrentIndex(max(0,strategy.findData(f.preprocess_strategy))); strategy.setToolTip(t("tooltip.field.strategy")); strategy_edits[f.id]=strategy; retry=QPushButton(t("dialog.recognition_review.retry")); retry.setToolTip(t("dialog.recognition_review.retry.tooltip")); retry.setShortcut(QKeySequence(f"Alt+{min(f.id,9)}")); row=QHBoxLayout(); row.addWidget(edit,1); row.addWidget(QLabel(t("ui.contrast"))); row.addWidget(contrast); row.addWidget(strategy); row.addWidget(retry)
            caption=f"{f.id}. {f.label or t('ui.field_label')}"
            if f.id in missing_ids:caption+=t("dialog.auto_empty.missing_mark")
            form.addRow(caption,row)
            def retry_field(_=False,field=f,target=edit,contrast_widget=contrast,strategy_widget=strategy,retry_button=retry):
                field.contrast=contrast_widget.value(); field.preprocess_strategy=strategy_widget.currentData()
                retry_engine=dict(self.config["engine"]); retry_engine["auto_deskew"]=self.deskew.isChecked(); retry_button.setEnabled(False); worker=RecognitionWorker(self.pdf_path,page,self.fields,retry_engine,self.ocr_cb.isChecked(),[field.id],self.pdf.textful); retry_workers.append(worker)
                def finished(_page,results,error,worker=worker):
                    hits=list(results.get(field.id,[]) or []) if not error else []; field.candidates[page]=[text for text in hits if str(text).strip()]
                    chosen=self.choose_candidate(hits,field)
                    if chosen is not None:self.fill_choice_combo(target,hits,self.effective_default(field,page),chosen); refresh_name()
                    retry_button.setEnabled(True)
                    if worker in retry_workers:retry_workers.remove(worker)
                    if worker.isRunning():worker.wait(60000)
                    worker.deleteLater()
                worker.completed.connect(finished,Qt.ConnectionType.QueuedConnection); worker.start()
            edit.activated.connect(lambda index,target=edit:self.apply_choice_combo_item(target,index)); retry.clicked.connect(retry_field)
        form.addRow(t("ui.name_preview"),filename_edit)
        def refresh_name():
            values={f.id:self.combo_choice_value(edits[f.id]).strip() for f in self.fields}; slot=self.page_save_slot.get(page,self.save_index)
            filename_edit.setText(sanitize_filename(expand_template_safe(template_edit.text(),values,page,slot),page+1)+".pdf")
        for edit in edits.values():edit.editTextChanged.connect(refresh_name); edit.activated.connect(lambda *_:refresh_name())
        template_edit.textEdited.connect(refresh_name)
        message=QLabel(); layout.addWidget(message); buttons=QHBoxLayout(); apply_btn=QPushButton(t("dialog.manual.apply" if manual else "dialog.auto_empty.apply")); apply_btn.setDefault(True); apply_btn.setAutoDefault(True); skip_btn=QPushButton(t("dialog.auto_empty.skip")); skip_btn.setShortcut(QKeySequence("Alt+S")); cancel_btn=QPushButton(t("dialog.manual.cancel" if manual else "dialog.auto_empty.cancel"))
        for button in (apply_btn,skip_btn,cancel_btn): buttons.addWidget(button)
        layout.addLayout(buttons); result={"value":"cancel"}
        def apply_values():
            if retry_workers:message.setText(t("status.recognizing")); return
            if any(not self.combo_choice_value(edit).strip() for edit in edits.values()): message.setText(t("dialog.auto_empty.required")); return
            if not filename_edit.text().strip():message.setText(t("dialog.auto_empty.filename_required")); return
            self.template.setText(template_edit.text())
            for f in self.fields:
                f.values[page]=self.combo_choice_value(edits[f.id]).strip(); f.statuses[page]="manual"; f.contrast=contrast_edits[f.id].value(); f.preprocess_strategy=strategy_edits[f.id].currentData()
                remember_applied_value(f,f.values[page])
            self.refresh_field_list(); self.filename.setText(filename_edit.text().strip()); result["value"]="apply"; dialog.accept()
        def close_with(value,accept):
            if retry_workers:message.setText(t("status.recognizing")); return
            result["value"]=value; (dialog.accept if accept else dialog.reject)()
        apply_btn.clicked.connect(apply_values); skip_btn.clicked.connect(lambda:close_with("skip",True)); cancel_btn.clicked.connect(lambda:close_with("cancel",False))
        enter_shortcut=QShortcut(QKeySequence(Qt.Key.Key_Return),dialog); enter_shortcut.activated.connect(apply_btn.click)
        num_enter_shortcut=QShortcut(QKeySequence(Qt.Key.Key_Enter),dialog); num_enter_shortcut.activated.connect(apply_btn.click)
        escape_shortcut=QShortcut(QKeySequence(Qt.Key.Key_Escape),dialog); escape_shortcut.activated.connect(cancel_btn.click)
        tab_order=[template_edit]
        for f in self.fields:tab_order.extend([edits[f.id],contrast_edits[f.id],strategy_edits[f.id]])
        tab_order.extend([filename_edit,apply_btn,skip_btn,cancel_btn])
        for first,second in zip(tab_order,tab_order[1:]):dialog.setTabOrder(first,second)
        self.exec_session_dialog("review",dialog,modal=False); return result["value"]
    def save_profile_file(self):
        p=self.profile_path
        if not p:
            x,_=QFileDialog.getSaveFileName(self,t("ui.save_profile"),"","Listorez2047 profile (*.pdfocr.json)"); p=Path(x) if x else None
        if not p:return
        self.sync_rects(); self.persist_output(save=False)
        try:
            save_profile(p,fields=self.fields,name_template=self.template.text(),page_format=self.page_format.currentText(),custom_mm=self.custom_mm(),orientation="portrait",ocr_enabled=self.ocr_cb.isChecked(),auto_deskew=self.deskew.isChecked(),engine=self.config["engine"],ui={k:self.config[k] for k in ("ui_language","ui_skin","ui_icon","ui_icon_locked")},output_folder=self.out_edit.text().strip(),output_relative=self.out_relative.isChecked())
            self.profile_path=p; self.persist()
        except Exception:
            LOGGER.exception("Profile save failed: %s",p); self.fail(t("error.profile"))
    def load_profile_file(self):
        x,_=QFileDialog.getOpenFileName(self,t("ui.load_profile"),"","Listorez2047 profile (*.json)")
        if not x:return
        try:
            if self.fields and QMessageBox.question(self,t("ui.load_profile"),t("dialog.profile.replace"))!=QMessageBox.StandardButton.Yes:return
            d=load_profile(Path(x)); self.fields=d["fields"]; self.template.setText(d.get("name_template","")); self.page_format.setCurrentText(d.get("page_format","from_pdf")); self.custom_unit.setCurrentText("mm"); self.custom_w.setValue(float(d.get("page_width_mm") or 210)); self.custom_h.setValue(float(d.get("page_height_mm") or 297)); self.ocr_cb.setChecked(bool(d.get("ocr_enabled",True))); self.deskew.setChecked(bool(d.get("auto_deskew",True))); self.config["engine"].update(d.get("engine",{})); self.config["engine"]["default_preprocess_strategy"]=valid_preprocess_strategy(self.config["engine"].get("default_preprocess_strategy"))
            for key,(minimum,maximum) in ENGINE_LIMITS.items():
                value=self.config["engine"].get(key,DEFAULT_ENGINE[key])
                try:value=float(value) if isinstance(DEFAULT_ENGINE[key],float) else int(value)
                except (TypeError,ValueError,OverflowError):value=DEFAULT_ENGINE[key]
                self.config["engine"][key]=max(minimum,min(maximum,value))
            for k in ("ui_language","ui_skin","ui_icon","ui_icon_locked"):
                if k in d:self.config[k]=d[k]
            if "output_folder" in d:self.out_edit.setText(str(d.get("output_folder") or ""))
            if "output_relative" in d:self.out_relative.setChecked(bool(d.get("output_relative")))
            set_language(self.config["ui_language"]); self.apply_appearance(); self.retranslate(); self.preview.set_fields(self.fields); self.refresh_field_list(); self.profile_path=Path(x); self.persist()
        except Exception:self.fail(t("error.profile"))
    def remember_window(self,key,widget):
        if widget is None:return
        g=widget.geometry(); remember_geometry(self.window_pos,key,g.x(),g.y(),g.width(),g.height())
    def restore_window(self,key,widget):
        box=stored_geometry(self.window_pos,key)
        if not box or widget is None:return
        screen=widget.screen() or QGuiApplication.primaryScreen()
        if screen:
            avail=screen.availableGeometry(); box=clamp_geometry(box,avail.x(),avail.y(),avail.width(),avail.height())
        widget.setGeometry(box["x"],box["y"],box["w"],box["h"])
    def center_window(self,widget):
        if widget is None:return
        screen=widget.screen() or QGuiApplication.primaryScreen()
        if not screen:return
        avail=screen.availableGeometry(); g=widget.frameGeometry(); widget.move(avail.center().x()-g.width()//2,avail.center().y()-g.height()//2)
    def show_session_widget(self,key,widget):
        widget.show(); self.restore_window(key,widget)
    def hide_session_widget(self,key,widget):
        self.remember_window(key,widget); widget.hide()
    def close_session_widget(self,key,widget):
        self.remember_window(key,widget); widget.close()
    def exec_session_dialog(self,key,dialog,modal=True):
        if modal:
            dialog.setModal(True); dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        else:
            dialog.setModal(False); dialog.setWindowModality(Qt.WindowModality.NonModal); dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,True)
        self.restore_window(key,dialog); QTimer.singleShot(0,lambda:self.restore_window(key,dialog))
        code=dialog.exec(); self.remember_window(key,dialog); return code
    def reset_window_positions(self):
        reset_geometries(self.window_pos)
        widgets=[]
        if self.auto_state and self.auto_state.get("progress"):widgets.append(self.auto_state["progress"])
        for extra in (self.help,self.cheat):
            if extra:widgets.append(extra)
        sender=self.sender()
        if sender is not None:
            win=sender.window()
            if win is not None and win is not self and win not in widgets:widgets.append(win)
        for widget in widgets:self.center_window(widget)
        self.statusBar().showMessage(t("config.reset_windows.done"))
    def show_config(self):
        d=ConfigDialog(self,self.config)
        if self.exec_session_dialog("config",d):
            self.config["engine"]=d.engine; self.config["logging_enabled"]=d.logging_enabled.isChecked(); self.config["log_path"]=d.log_path.text().strip(); self.config["log_levels"]=d.selected_log_levels(); self.persist()
            try:
                from .app_logging import setup_logging
                setup_logging(self.config)
            except OSError:self.fail(t("error.log"))
            self.preload_engine()
    def show_help(self):
        if not self.help:self.help=HelpWindow(self)
        self.help.show(); self.help.raise_()
    def show_cheat(self):
        if not self.cheat:self.cheat=HelpWindow(self,True); self.cheat.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,True)
        self.cheat.setVisible(not self.cheat.isVisible())
    def about(self):QMessageBox.about(self,t("menu.help.about"),t("about.body"))
    def fail(self,message):
        LOGGER.error("%s",message,exc_info=True)
        QMessageBox.critical(self,t("app.name"),message)
    def closeEvent(self,e):
        LOGGER.info("Main window closing")
        if self.auto_state:
            self.auto_state["cancelled"]=True
            try:self.close_session_widget("auto_progress",self.auto_state["progress"])
            except Exception:LOGGER.exception("Failed to close Auto progress")
            self.auto_state=None
        for loader in list(self.engine_loaders):
            if loader.isRunning():loader.wait(60000)
        self.release_worker()
        if self.pdf:self.pdf.close()
        self.persist(); super().closeEvent(e)
