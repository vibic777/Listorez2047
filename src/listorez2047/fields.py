from __future__ import annotations
from dataclasses import dataclass, field
import math

@dataclass
class Field:
    id:int; label:str=""; pattern:str=""; rect:dict=field(default_factory=lambda:{"x":.1,"y":.1,"w":.3,"h":.08})
    ocr_langs:list[str]=field(default_factory=list); overlap_mode:str="recognize"; contrast:float=1.0; preprocess_strategy:str="standard"; default_value:str=""; default_is_expression:bool=False; remember_last_value:bool=True
    values:dict[int,str]=field(default_factory=dict); statuses:dict[int,str]=field(default_factory=dict); candidates:dict[int,list[str]]=field(default_factory=dict)
    def value(self,page:int)->str: return self.values.get(page,"")
    def portable(self)->dict:
        return {"id":self.id,"label":self.label,"pattern":self.pattern,"rect":dict(self.rect),
                "ocr_langs":list(self.ocr_langs),"overlap_mode":self.overlap_mode,"contrast":self.contrast,"preprocess_strategy":self.preprocess_strategy,"default_value":self.default_value,
                "default_is_expression":self.default_is_expression,"remember_last_value":self.remember_last_value}
    @classmethod
    def from_dict(cls,d:dict):
        if not isinstance(d,dict):raise ValueError("Field must be an object")
        rect=d.get("rect") or {"x":.1,"y":.1,"w":.3,"h":.08}
        if not isinstance(rect,dict):raise ValueError("Field rectangle must be an object")
        try:
            x,y,w,h=(float(rect[k]) for k in ("x","y","w","h"))
            field_id=int(d.get("id",1)); contrast=float(d.get("contrast",1.0))
        except (KeyError,TypeError,ValueError,OverflowError) as exc:
            raise ValueError("Invalid field geometry or id") from exc
        if not all(math.isfinite(v) for v in (x,y,w,h,contrast)):
            raise ValueError("Field values must be finite")
        if field_id<1 or x<0 or y<0 or w<=0 or h<=0 or x+w>1.000001 or y+h>1.000001:
            raise ValueError("Field rectangle is outside page bounds")
        if not 1<=contrast<=4:raise ValueError("Field contrast must be between 1 and 4")
        langs=d.get("ocr_langs") or []
        if not isinstance(langs,list) or any(lang not in {"eslav","latin","chinese"} for lang in langs):
            raise ValueError("Invalid OCR languages")
        overlap=str(d.get("overlap_mode","recognize"))
        if overlap not in {"recognize","clip"}:raise ValueError("Invalid overlap mode")
        return cls(id=field_id,label=str(d.get("label","")),pattern=str(d.get("pattern","")),
                   rect={"x":x,"y":y,"w":w,"h":h},ocr_langs=list(langs),overlap_mode=overlap,
                   contrast=contrast,preprocess_strategy=str(d.get("preprocess_strategy","standard")),default_value=str(d.get("default_value","") or ""),
                   default_is_expression=bool(d.get("default_is_expression",False)),remember_last_value=bool(d.get("remember_last_value",True)))

def remember_applied_value(field:Field,value:str)->None:
    """Store the last confirmed value as the next-page default. OCR hits are ignored until Apply/Save."""
    if not field.remember_last_value:return
    text=(value or "").strip()
    if text:field.default_value=text

def field_choice_items(scan_hits:list[str]|None,default_value:str="")->list[tuple[str,str]]:
    """Unique dropdown rows: OCR/scan results first, then the field default if it differs."""
    items=[]; seen:set[str]=set()
    for hit in scan_hits or []:
        text=(hit or "").strip()
        if text and text not in seen:
            items.append(("scan",text)); seen.add(text)
    default=(default_value or "").strip()
    if default and default not in seen:items.append(("default",default))
    return items

def empty_fields(fields:list[Field],page:int)->list[Field]:
    """Fields that must be resolved before Auto may save this page."""
    return [item for item in fields if item.statuses.get(page) in {"empty","ambiguous"} or not item.value(page).strip()]

def auto_page_plan(status:str)->str:
    """Return skip, reuse, or recognize for a subsequent Auto run."""
    if status in {"saved","skipped"}: return "skip"
    if status == "recognized": return "reuse"
    return "recognize"
