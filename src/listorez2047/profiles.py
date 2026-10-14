from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from .fields import Field

PAGE_UNIT_MM={"mm":1.0,"cm":10.0,"in":25.4}

def convert_page_value(value:float,old_unit:str,new_unit:str)->float:
    return value*PAGE_UNIT_MM[old_unit]/PAGE_UNIT_MM[new_unit]

def save_profile(path:Path, *, fields:list[Field], name_template:str, page_format:str,
                 custom_mm:tuple[float,float], orientation:str, ocr_enabled:bool,
                 auto_deskew:bool, engine:dict, ui:dict, name:str="",
                 output_folder:str="", output_relative:bool=False) -> None:
    data={"format_version":1,"name":name,"name_template":name_template,"page_format":page_format,
      "page_width_mm":custom_mm[0] if page_format=="custom" else None,
      "page_height_mm":custom_mm[1] if page_format=="custom" else None,
      "page_orientation":orientation,"ocr_enabled":ocr_enabled,"auto_deskew":auto_deskew,
      "output_folder":output_folder,"output_relative":bool(output_relative),
      "fields":[f.portable() for f in fields],"engine":dict(engine),**ui}
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(data,ensure_ascii=False,indent=2)
    fd,temp_name=tempfile.mkstemp(prefix=f".{path.name}.",suffix=".tmp",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp_name,path)
    except Exception:
        try:os.unlink(temp_name)
        except OSError:pass
        raise

def resolve_output_dir(stored:str, *, relative:bool, base:Path|None=None)->Path:
    """Absolute folder, or relative to base (PDF folder / cwd)."""
    text=(stored or "").strip()
    if not text:return Path()
    path=Path(text)
    if path.is_absolute() or not relative:return path
    root=base if base is not None else Path.cwd()
    return (root / path).resolve()

def load_profile(path:Path)->dict:
    d=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(d,dict):raise ValueError("Profile must be an object")
    if d.get("format_version") != 1: raise ValueError("Unsupported profile format")
    fields=d.get("fields",[])
    if not isinstance(fields,list):raise ValueError("Profile fields must be a list")
    d["fields"]=[Field.from_dict(x) for x in fields]
    if len({field.id for field in d["fields"]})!=len(d["fields"]):raise ValueError("Field ids must be unique")
    engine=d.get("engine",{})
    if not isinstance(engine,dict):raise ValueError("Profile engine settings must be an object")
    d["engine"]=engine
    d["engine"]["ocr_engine"]="rapidocr"
    if not any(d["engine"].get(key,True if key=="lang_eslav" else False) for key in ("lang_eslav","lang_latin","lang_chinese")):
        d["engine"]["lang_eslav"]=True
    return d
