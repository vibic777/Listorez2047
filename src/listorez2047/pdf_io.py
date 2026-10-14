from __future__ import annotations
from pathlib import Path
import os
import tempfile
import pymupdf as fitz

class PdfDocument:
    def __init__(self,path:Path,textful:list[bool]|None=None):
        self.path=Path(path); self.doc=fitz.open(path)
        if self.doc.needs_pass: self.doc.close(); raise PermissionError("encrypted")
        try:
            # Auto recognition already indexed the open document. Reuse that
            # immutable snapshot in short-lived worker handles instead of
            # extracting every page's text again for every page processed.
            if textful is not None and len(textful)==len(self.doc):
                self.textful=list(textful)
            else:
                self.textful=[self._useful(i) for i in range(len(self.doc))]
        except Exception:
            self.doc.close()
            raise
    def _useful(self,i:int)->bool:
        # A short but meaningful page can still be a native-text PDF. Ignore
        # only truly empty/near-empty text layers (the TZ's 1-2 space case).
        return bool("".join(self.doc[i].get_text().split()))
    @property
    def kind(self):
        return "digital" if all(self.textful) else "scan" if not any(self.textful) else "mixed"
    def render(self,i:int,dpi:int=110,rotation:float=0,rect=None,max_side:int|None=None):
        page=self.doc[i]
        if rect is None:
            area=page.rect
        else:
            if min(rect.x,rect.y,rect.w,rect.h)<0 or rect.w<=0 or rect.h<=0:return None
            area=fitz.Rect(rect.x*page.rect.width,rect.y*page.rect.height,
                           (rect.x+rect.w)*page.rect.width,(rect.y+rect.h)*page.rect.height)
            area=area & page.rect
            if area.is_empty:return None
        scale=dpi/72
        if max_side and max(area.width,area.height)*scale>max_side:
            scale=max_side/max(area.width,area.height)
        if rect is not None:
            return page.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=area,alpha=False)
        matrix=fitz.Matrix(scale,scale).prerotate(rotation)
        return page.get_pixmap(matrix=matrix,alpha=False)
    def text_in_rects(self,i:int,rects:list, padding_pct:float=0)->str:
        page=self.doc[i]; pr=page.rect; words=page.get_text("words"); found=[]
        expanded=[]
        for r in rects:
            pad=max(r.w*pr.width,r.h*pr.height)*padding_pct/100
            box=fitz.Rect(r.x*pr.width-pad,r.y*pr.height-pad,(r.x+r.w)*pr.width+pad,(r.y+r.h)*pr.height+pad)
            expanded.append(box)
        for w in words:
            word_box=fitz.Rect(w[:4])
            if any(word_box.intersects(box) for box in expanded):found.append((w[1],w[0],w[4]))
        return " ".join(x[2] for x in sorted(set(found)))
    def save_page(self,i:int,path:Path,rotation:float=0):
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
        out=fitz.open(); temp_path=None
        try:
            out.insert_pdf(self.doc,from_page=i,to_page=i)
            if rotation: out[0].set_rotation((out[0].rotation+round(rotation/90)*90)%360)
            fd,temp_name=tempfile.mkstemp(prefix=f".{path.stem}.",suffix=".tmp",dir=path.parent)
            os.close(fd); temp_path=Path(temp_name)
            out.save(temp_path)
            # Do not overwrite if another process created the destination.
            try:os.link(temp_path,path)
            except OSError:
                if path.exists():raise FileExistsError(path)
                os.replace(temp_path,path); temp_path=None
        finally:
            out.close()
            if temp_path is not None:
                try:temp_path.unlink()
                except FileNotFoundError:pass
    def close(self): self.doc.close()
