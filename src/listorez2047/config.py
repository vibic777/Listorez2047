"""Local configuration and packaged-resource paths."""
from __future__ import annotations
import json, os, sys
from pathlib import Path

DEFAULT_ENGINE = {"ocr_engine":"rapidocr","dpi":300,"ocr_max_side":3508,"cpu_threads":2,"use_angle_cls":True,
 "drop_score":.50,"det_limit_side_len":1280,"rec_batch_num":6,"lang_eslav":True,
 "lang_latin":False,"lang_chinese":False,"prefer_native_text":True,"field_padding_pct":5,"ocr_contrast":1.0,
 "default_preprocess_strategy":"standard","auto_deskew":True}
ENGINE_LIMITS = {"dpi":(100,600),"ocr_max_side":(800,10000),"cpu_threads":(1,4),
 "drop_score":(0,1),"det_limit_side_len":(320,4096),"rec_batch_num":(1,32),
 "field_padding_pct":(0,50),"ocr_contrast":(1,4)}
DEFAULT_UI = {"ui_language":"ru","ui_skin":"it_gray","ui_icon":"it","ui_icon_locked":False}
APP_DIR_NAME = "Listorez2047"
LEGACY_APP_DIRS = ("Listorez", "PDFOCRsplitter")
LEGACY_LOG_NAMES = {"PDFOCRSplitter.log", "Listorez.log"}

def _settings_root() -> Path:
    return Path(os.environ.get("APPDATA", Path.home() / ".config"))

def default_log_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "Listorez2047.log"
    return _settings_root() / APP_DIR_NAME / "Listorez2047.log"

def resource_path(*parts: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root.joinpath(*parts)

def config_path() -> Path:
    exe_dir = Path(sys.executable).resolve().parent
    portable = exe_dir / "config.json"
    if portable.exists(): return portable
    return _settings_root() / APP_DIR_NAME / "config.json"

def migrate_log_path(stored) -> str:
    """Keep a custom folder; only rename leftover log filenames from older builds."""
    try:
        path = Path(str(stored))
    except (TypeError, ValueError):
        return str(default_log_path())
    if path.name in LEGACY_LOG_NAMES:
        return str(path.with_name("Listorez2047.log"))
    return str(path)

def existing_config_path() -> Path:
    path = config_path()
    if path.exists():
        return path
    if path != _settings_root() / APP_DIR_NAME / "config.json":
        return path
    for name in LEGACY_APP_DIRS:
        candidate = _settings_root() / name / "config.json"
        if candidate.exists():
            return candidate
    return path

def defaults() -> dict:
    from .app_logging import default_log_levels
    return {"engine":dict(DEFAULT_ENGINE), **DEFAULT_UI,"logging_enabled":False,
            "log_path":str(default_log_path()),"log_levels":default_log_levels(),
            "output_folder":"","output_relative":False}

def load_config() -> dict:
    from .app_logging import normalize_log_levels
    data = defaults(); path = existing_config_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        data.update({k:v for k,v in raw.items() if k != "engine"})
        data["engine"].update(raw.get("engine", {}))
    except (OSError, ValueError, TypeError): pass
    data["log_path"] = migrate_log_path(data.get("log_path") or default_log_path())
    data["logging_enabled"] = bool(data.get("logging_enabled", False))
    data["log_levels"] = normalize_log_levels(data.get("log_levels"))
    data["output_folder"] = str(data.get("output_folder") or "")
    data["output_relative"] = bool(data.get("output_relative", False))
    for key,(minimum,maximum) in ENGINE_LIMITS.items():
        default=DEFAULT_ENGINE[key]
        try:value=float(data["engine"].get(key,default)) if isinstance(default,float) else int(data["engine"].get(key,default))
        except (TypeError,ValueError):value=default
        data["engine"][key]=max(minimum,min(maximum,value))
    if not any(data["engine"].get(k) for k in ("lang_eslav","lang_latin","lang_chinese")):
        data["engine"]["lang_eslav"] = True
    # Surya was removed; migrate old profiles/configuration without failing.
    data["engine"]["ocr_engine"] = "rapidocr"
    data["engine"]["default_preprocess_strategy"] = valid_preprocess_strategy(data["engine"].get("default_preprocess_strategy"))
    if "auto_deskew" not in data["engine"]:
        data["engine"]["auto_deskew"] = True
    else:
        data["engine"]["auto_deskew"] = bool(data["engine"].get("auto_deskew"))
    return data

def valid_preprocess_strategy(value)->str:
    from .ocr_engine import OCR_STRATEGIES
    strategy=str(value or "standard")
    return strategy if strategy in OCR_STRATEGIES else "standard"

def save_config(data: dict) -> None:
    path=config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        # A read-only portable medium must not prevent the app from closing.
        return

def remember_geometry(store:dict,key:str,x:int,y:int,w:int,h:int)->None:
    """Session-only window box. Ignored if the size is not usable."""
    if w>40 and h>40:store[key]={"x":int(x),"y":int(y),"w":int(w),"h":int(h)}

def stored_geometry(store:dict,key:str)->dict|None:
    box=store.get(key)
    if not isinstance(box,dict):return None
    try:x,y,w,h=int(box["x"]),int(box["y"]),int(box["w"]),int(box["h"])
    except (KeyError,TypeError,ValueError):return None
    if w<=40 or h<=40:return None
    return {"x":x,"y":y,"w":w,"h":h}

def reset_geometries(store:dict)->None:
    store.clear()

def clamp_geometry(box:dict,sx:int,sy:int,sw:int,sh:int)->dict:
    """Keep a stored box inside the given screen rectangle."""
    w=max(41,min(int(box["w"]),max(41,sw)))
    h=max(41,min(int(box["h"]),max(41,sh)))
    x=max(sx,min(int(box["x"]),sx+max(0,sw-w)))
    y=max(sy,min(int(box["y"]),sy+max(0,sh-h)))
    return {"x":x,"y":y,"w":w,"h":h}
