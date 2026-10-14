from __future__ import annotations
import logging
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QImage, QPixmap, QPen, QBrush, QColor
from PySide6.QtWidgets import QGraphicsView,QGraphicsScene,QGraphicsRectItem,QGraphicsSimpleTextItem

_LOG=logging.getLogger("listorez2047.preview")

class FieldRectItem(QGraphicsRectItem):
    def __init__(self,field_id:int,rect:QRectF):
        super().__init__(rect); self.field_id=field_id
        self.setFlags(self.GraphicsItemFlag.ItemIsMovable|self.GraphicsItemFlag.ItemIsSelectable|self.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPen(QPen(QColor("#e53935"),2)); self.setBrush(QBrush(QColor(229,57,53,25)))
        self.label=QGraphicsSimpleTextItem(str(field_id),self); self.label.setBrush(QBrush(Qt.GlobalColor.red)); self.label.setPos(rect.topLeft())
        self._resizing=False
    def _near_handle(self,pos):
        r=self.rect(); return abs(pos.x()-r.right())<=24 and abs(pos.y()-r.bottom())<=24
    def mousePressEvent(self,event):
        self._resizing=self._near_handle(event.pos())
        if self._resizing: event.accept(); return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._resizing:
            r=self.rect(); p=event.pos(); r.setRight(max(r.left()+20,p.x())); r.setBottom(max(r.top()+20,p.y())); self.setRect(r); self.label.setPos(r.topLeft()); event.accept(); return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        self._resizing=False; super().mouseReleaseEvent(event)
    def paint(self,painter,option,widget=None):
        super().paint(painter,option,widget)
        if self.isSelected():
            r=self.rect(); painter.fillRect(QRectF(r.right()-18,r.bottom()-18,18,18),QColor("#ffffff")); painter.setPen(QPen(QColor("#e53935"),3)); painter.drawRect(QRectF(r.right()-18,r.bottom()-18,18,18))

class PreviewView(QGraphicsView):
    rect_drawn=Signal(object); rects_changed=Signal(); field_selected=Signal(int)
    def __init__(self):
        super().__init__(); self.setScene(QGraphicsScene(self)); self.setDragMode(self.DragMode.ScrollHandDrag)
        self._pix=None; self._drawing=False; self._start=None; self._rubber=None; self._items=[]; self._has_view=False; self._default_view=None; self._updating=False
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse); self.scene().selectionChanged.connect(self._selection_changed)
    def _selection_changed(self):
        selected=[x for x in self.scene().selectedItems() if isinstance(x,FieldRectItem)]
        if selected:self.field_selected.emit(selected[0].field_id)
    def set_pixmap_data(self,samples:bytes,width:int,height:int,stride:int):
        self._updating=True
        try:
            old=self.sceneRect(); center=self.mapToScene(self.viewport().rect().center())
            normalized=(center.x()/old.width(),center.y()/old.height()) if self._has_view and old.width() and old.height() else None
            transform=self.transform()
            if self._default_view:transform,normalized=self._default_view
            image=QImage(samples,width,height,stride,QImage.Format.Format_RGB888).copy()
            self.scene().clear(); self._items=[]; self._pix=self.scene().addPixmap(QPixmap.fromImage(image)); self.scene().setSceneRect(self._pix.boundingRect())
            if normalized:
                self.setTransform(transform); b=self.sceneRect(); self.centerOn(normalized[0]*b.width(),normalized[1]*b.height())
            else:self.fit()
        except Exception:
            _LOG.exception("Failed to update preview pixmap %sx%s",width,height)
        finally:
            self._updating=False
    def set_fields(self,fields):
        if not self._pix:return
        for i in self._items:self.scene().removeItem(i)
        self._items=[]; b=self._pix.boundingRect()
        for f in fields:
            r=f.rect; item=FieldRectItem(f.id,QRectF(r['x']*b.width(),r['y']*b.height(),r['w']*b.width(),r['h']*b.height()))
            self.scene().addItem(item); self._items.append(item)
    def normalized_rects(self):
        if not self._pix:return {}
        b=self._pix.boundingRect(); return {i.field_id:{'x':i.rect().x()/b.width()+i.pos().x()/b.width(),'y':i.rect().y()/b.height()+i.pos().y()/b.height(),'w':i.rect().width()/b.width(),'h':i.rect().height()/b.height()} for i in self._items}
    def select_field(self,field_id:int):
        for item in self._items:item.setSelected(item.field_id==field_id)
    def start_drawing(self): self._drawing=True; self.setDragMode(self.DragMode.NoDrag)
    def mousePressEvent(self,e):
        if self._drawing and e.button()==Qt.MouseButton.LeftButton:
            self._start=self.mapToScene(e.position().toPoint()); self._rubber=QGraphicsRectItem(); self._rubber.setPen(QPen(Qt.GlobalColor.red,2,Qt.PenStyle.DashLine)); self.scene().addItem(self._rubber); return
        super().mousePressEvent(e)
    def mouseMoveEvent(self,e):
        if self._drawing and self._rubber:
            self._rubber.setRect(QRectF(self._start,self.mapToScene(e.position().toPoint())).normalized()); return
        super().mouseMoveEvent(e)
    def mouseReleaseEvent(self,e):
        if self._drawing and self._rubber:
            r=self._rubber.rect().intersected(self.sceneRect()); self.scene().removeItem(self._rubber); self._rubber=None; self._drawing=False; self.setDragMode(self.DragMode.ScrollHandDrag)
            if r.width()>5 and r.height()>5:
                b=self.sceneRect(); self.rect_drawn.emit({'x':r.x()/b.width(),'y':r.y()/b.height(),'w':r.width()/b.width(),'h':r.height()/b.height()})
            return
        super().mouseReleaseEvent(e); self.rects_changed.emit()
    def wheelEvent(self,e):
        if self._updating:return
        self._has_view=True; self.scale(1.2 if e.angleDelta().y()>0 else 1/1.2,1.2 if e.angleDelta().y()>0 else 1/1.2)
    def zoom(self,f):
        if self._updating:return
        try:self._has_view=True; self.scale(f,f); _LOG.debug("Preview zoom factor=%s",f)
        except Exception:_LOG.exception("Preview zoom failed")
    def fit(self):
        if self._updating:return
        try:
            if self._pix:self.fitInView(self._pix,Qt.AspectRatioMode.KeepAspectRatio); self._has_view=True; _LOG.debug("Preview fit")
        except Exception:_LOG.exception("Preview fit failed")
    def save_default_view(self):
        try:
            b=self.sceneRect(); center=self.mapToScene(self.viewport().rect().center())
            if b.width() and b.height():self._default_view=(self.transform(),(center.x()/b.width(),center.y()/b.height())); _LOG.info("Preview view saved")
        except Exception:_LOG.exception("Preview save view failed")
    def reset_view(self):self._has_view=False; self._default_view=None; self.resetTransform()
