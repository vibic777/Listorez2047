"""Sequential, CPU-only extraction. RapidOCR is imported lazily."""
from __future__ import annotations
import logging
from threading import RLock
import gc
from .config import resource_path
from .overlap import Rect,effective_rects

_LOG=logging.getLogger("listorez2047.ocr")
_rapidocr=None
_backend_lock=RLock()
_ENGINE_SIGNATURE=None
OCR_STRATEGIES=("standard","clahe","paper_normalize","adaptive","remove_lines","upscale_sharpen")

_MODEL_FILES={"eslav":"eslav_PP-OCRv5_rec_mobile.onnx","latin":"latin_PP-OCRv5_rec_mobile.onnx",
              "chinese":"ch_PP-OCRv5_rec_mobile.onnx"}
_LANG_CODES={"eslav":"eslav","latin":"latin","chinese":"ch"}

def _selected_languages(engine,field):
    selected=[key for key in (getattr(field,"ocr_langs",[]) or []) if engine.get("lang_"+key,False)]
    if not selected:
        selected=[key for key in _MODEL_FILES if engine.get("lang_"+key,False)]
    return selected or ["eslav"]

def _create_engine(lang,engine):
    from rapidocr import EngineType,LangCls,LangDet,LangRec,ModelType,OCRVersion,RapidOCR
    root=resource_path("assets","models")
    missing=[name for name in ("ch_PP-OCRv5_det_mobile.onnx",
        "ch_PP-LCNet_x0_25_textline_ori_cls_mobile.onnx",_MODEL_FILES[lang]) if not (root/name).is_file()]
    if missing:
        raise RuntimeError("Bundled PP-OCRv5 models are missing: "+", ".join(missing))
    common={"engine_type":EngineType.ONNXRUNTIME,"ocr_version":OCRVersion.PPOCRV5}
    params={
        "Global.log_level":"error",
        "EngineConfig.onnxruntime.use_cuda":False,
        "EngineConfig.onnxruntime.use_dml":False,
        "EngineConfig.onnxruntime.intra_op_num_threads":max(1,min(4,int(engine.get("cpu_threads",2)))),
        "EngineConfig.onnxruntime.inter_op_num_threads":1,
        "Det.engine_type":common["engine_type"],"Det.lang_type":LangDet.CH,"Det.model_type":ModelType.MOBILE,
        "Det.ocr_version":common["ocr_version"],"Det.model_path":str(root/"ch_PP-OCRv5_det_mobile.onnx"),
        "Det.limit_side_len":max(320,min(4096,int(engine.get("det_limit_side_len",1280)))),
        "Cls.engine_type":common["engine_type"],"Cls.lang_type":LangCls.CH,"Cls.model_type":ModelType.MOBILE,
        "Cls.ocr_version":common["ocr_version"],"Cls.model_path":str(root/"ch_PP-LCNet_x0_25_textline_ori_cls_mobile.onnx"),
        "Rec.engine_type":common["engine_type"],"Rec.lang_type":LangRec(_LANG_CODES[lang]),"Rec.model_type":ModelType.MOBILE,
        "Rec.ocr_version":common["ocr_version"],"Rec.model_path":str(root/_MODEL_FILES[lang]),
        "Rec.rec_batch_num":max(1,min(32,int(engine.get("rec_batch_num",6)))),
        "Global.text_score":float(engine.get("drop_score",.5)),
        "Global.max_side_len":max(800,min(10000,int(engine.get("ocr_max_side",3508)))),
    }
    return RapidOCR(params=params)

def preload_backend(name:str,engine=None,lang="eslav"):
    global _rapidocr,_ENGINE_SIGNATURE
    engine=engine or {}
    with _backend_lock:
        signature=(lang,int(engine.get("cpu_threads",2)),int(engine.get("det_limit_side_len",1280)),int(engine.get("rec_batch_num",6)),int(engine.get("ocr_max_side",3508)),float(engine.get("drop_score",.5)))
        if name in ("rapidocr","both") and (_rapidocr is None or signature!=_ENGINE_SIGNATURE):
            _rapidocr=None
            gc.collect()
            _rapidocr=_create_engine(lang,engine)
            _ENGINE_SIGNATURE=signature

def _run_rapidocr(crop,engine,lang):
    with _backend_lock:
        preload_backend("rapidocr",engine,lang)
        result=_rapidocr(crop,use_cls=bool(engine.get("use_angle_cls",True)))
        if result is None:return "",0.0
        scores=result.scores or (); texts=result.txts or ()
        kept=[(str(text),float(score)) for text,score in zip(texts,scores) if float(score)>=float(engine.get("drop_score",.5))]
        return " ".join(text for text,_ in kept),(sum(score for _,score in kept)/len(kept) if kept else 0.0)

def _handwriting_variant(image,kind):
    """Return a conservative alternate raster for weak handwriting reads."""
    import cv2
    gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY) if image.ndim==3 else image
    if kind=="local_contrast":
        # Preserve grayscale stroke detail; hard binarization can break cursive joins.
        gray=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)).apply(gray)
        smooth=cv2.GaussianBlur(gray,(0,0),0.8)
        gray=cv2.addWeighted(gray,1.35,smooth,-0.35,0)
    elif kind=="adaptive":
        short=min(gray.shape[:2]); block=min(31,short if short%2 else short-1)
        if block<3:return None
        gray=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,block,7)
    elif kind=="remove_lines":
        # Horizontal rules and underlines can merge with handwritten digits.
        ink=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
        width=max(12,gray.shape[1]//3)
        lines=cv2.morphologyEx(ink,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(width,1)))
        gray=255-cv2.subtract(ink,lines)
    else:
        return None
    # A modest enlargement helps small handwritten strokes. The OCR crop is
    # already capped, so keep the retry below roughly 5.3k px per side.
    if max(gray.shape[:2])<=3600:
        gray=cv2.resize(gray,None,fx=1.4,fy=1.4,interpolation=cv2.INTER_CUBIC)
    return cv2.cvtColor(gray,cv2.COLOR_GRAY2RGB)

def _run_rapidocr_candidates(crop,engine,lang,pattern=""):
    """Keep distinct OCR reads for review when a field looks uncertain."""
    from .pattern_dsl import find_all
    candidates=[_run_rapidocr(crop,engine,lang)]
    threshold=max(.72,min(.88,float(engine.get("drop_score",.5))+.32))
    baseline=candidates[0]
    height,width=crop.shape[:2]
    hits=find_all(baseline[0],pattern) if pattern else []
    suspiciously_short=("D" in pattern and width>=height*1.5 and any(hit.isdigit() and len(hit)==1 for hit in hits))
    if baseline[1]>=threshold and (not pattern or hits) and not suspiciously_short:
        return candidates
    for kind in ("local_contrast","adaptive","remove_lines"):
        variant=_handwriting_variant(crop,kind)
        if variant is None:continue
        try:
            candidate=_run_rapidocr(variant,engine,lang)
        finally:
            del variant
        _LOG.debug("OCR retry language=%s variant=%s score=%.3f",lang,kind,candidate[1])
        candidates.append(candidate)
    # Put pattern-compatible reads first, then prefer the model's higher score.
    # Keep other reads too: the review dialog lets a person resolve ambiguity.
    candidates.sort(key=lambda item:(bool(pattern and find_all(item[0],pattern)),item[1]),reverse=True)
    unique=[]; seen=set()
    for text,score in candidates:
        text=str(text or "").strip()
        if text and text not in seen:
            seen.add(text); unique.append((text,score))
    return unique

def _run_rapidocr_with_retry(crop,engine,lang):
    """Compatibility helper returning the best candidate only."""
    candidates=_run_rapidocr_candidates(crop,engine,lang)
    return candidates[0] if candidates else ("",0.0)

def _deskew(image):
    """Correct a small scan skew without changing page geometry or output PDF."""
    import cv2
    import numpy as np
    gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY) if image.ndim==3 else image
    ink=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    coords=np.column_stack(np.where(ink>0))
    if len(coords)<20:return image
    angle=cv2.minAreaRect(coords)[-1]
    angle=-(90+angle) if angle < -45 else -angle
    if not .15<=abs(angle)<=6:return image
    h,w=image.shape[:2]
    matrix=cv2.getRotationMatrix2D((w/2,h/2),angle,1.0)
    return cv2.warpAffine(image,matrix,(w,h),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_CONSTANT,borderValue=(255,255,255))

def field_regions(field,fields):
    r=Rect(**field.rect); others=[Rect(**x.rect) for x in fields if x.id!=field.id]
    return effective_rects(r,others,field.overlap_mode)

def recognize_field(pdf,page_index,field,fields,engine,ocr_enabled:bool)->list[str]:
    rects=field_regions(field,fields)
    if not rects:return []
    _LOG.debug("OCR field=%s page=%s ocr=%s",field.id,page_index+1,ocr_enabled)
    if (not ocr_enabled) or (engine.get("prefer_native_text",True) and pdf.textful[page_index]):
        native=pdf.text_in_rects(page_index,rects,float(engine.get("field_padding_pct",5)))
        if native or not ocr_enabled:return [native.strip()] if native.strip() else []
    # Prefer text-layer extraction before allocating OCR models or rasters.
    # Render only the field bounding box, bounded by the configured max side.
    try:
        import numpy as np
        left=min(r.x for r in rects); top=min(r.y for r in rects)
        right=max(r.x+r.w for r in rects); bottom=max(r.y+r.h for r in rects)
        bounds=Rect(left,top,right-left,bottom-top)
        dpi=max(100,min(600,int(engine.get("dpi",300))))
        padding_pct=max(0,min(50,float(engine.get("field_padding_pct",5))))
        pad=max(bounds.w,bounds.h)*padding_pct/100
        bounds=Rect(max(0,bounds.x-pad),max(0,bounds.y-pad),min(1,bounds.x+bounds.w+pad)-max(0,bounds.x-pad),min(1,bounds.y+bounds.h+pad)-max(0,bounds.y-pad))
        max_side=max(800,min(10000,int(engine.get("ocr_max_side",3508))))
        pix=pdf.render(page_index,dpi,rect=bounds,max_side=max_side)
        if pix is None:return []
        # PyMuPDF exposes immutable sample bytes; masking and deskew need an
        # owned writable array.
        # Build a writable raster explicitly. ndarray.copy() can still retain
        # a read-only flag when the source is backed by immutable PyMuPDF bytes
        # in some bundled NumPy builds; OCR masking below mutates this buffer.
        image=np.array(np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,pix.n),copy=True,order="C")
        if not image.flags.writeable:
            image.setflags(write=True)
        import cv2
        mask=np.zeros((pix.height,pix.width),dtype=np.uint8)
        text_regions=[]
        contrast=float(getattr(field,"contrast",1.0) or engine.get("ocr_contrast",1.0))
        strategy=getattr(field,"preprocess_strategy","standard")
        for region in rects:
            pad=max(region.w,region.h)*padding_pct/100
            rx=max(0,region.x-pad); ry=max(0,region.y-pad); rx2=min(1,region.x+region.w+pad); ry2=min(1,region.y+region.h+pad)
            x1=max(0,int((rx-bounds.x)/bounds.w*pix.width)); y1=max(0,int((ry-bounds.y)/bounds.h*pix.height))
            x2=min(pix.width,int((rx2-bounds.x)/bounds.w*pix.width)); y2=min(pix.height,int((ry2-bounds.y)/bounds.h*pix.height))
            if x2>x1 and y2>y1:
                mask[y1:y2,x1:x2]=255
                text_regions.append((x1,y1,x2,y2))
        if not np.any(mask):return []
        # White outside the effective OCR rectangles so excluded text is not
        # passed to RapidOCR's detector.
        image[mask==0]=255
        crop=image
        if engine.get("auto_deskew",True):crop=_deskew(crop)
        if contrast>1.01 or strategy!="standard":
            import cv2
            gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
            gray=cv2.createCLAHE(clipLimit=max(1.01,contrast),tileGridSize=(8,8)).apply(gray)
            if strategy=="paper_normalize":
                background=cv2.GaussianBlur(gray,(0,0),max(9,gray.shape[1]/35))
                gray=cv2.divide(gray,background,scale=255)
                gray=cv2.createCLAHE(clipLimit=max(2.0,contrast),tileGridSize=(6,6)).apply(gray)
                gray=cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
            elif strategy=="adaptive":
                gray=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,11)
            elif strategy=="remove_lines":
                ink=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
                kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(max(12,gray.shape[1]//3),1)); lines=cv2.morphologyEx(ink,cv2.MORPH_OPEN,kernel)
                gray=255-cv2.subtract(ink,lines)
            elif strategy=="upscale_sharpen":
                gray=cv2.resize(gray,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC); blur=cv2.GaussianBlur(gray,(0,0),1.2); gray=cv2.addWeighted(gray,1.8,blur,-.8,0)
            crop=cv2.cvtColor(gray,cv2.COLOR_GRAY2RGB)
        result_parts=[]
        selected_languages=_selected_languages(engine,field)
        if len(text_regions)>1 and getattr(field,"overlap_mode","recognize")=="clip":
            # Separate disconnected clipped regions so the detector cannot
            # bridge across a masked hole and join unrelated glyphs.
            clipped_parts=[]
            for x1,y1,x2,y2 in text_regions:
                part=crop[y1:y2,x1:x2]
                alternatives=[_run_rapidocr_with_retry(part,engine,lang) for lang in selected_languages]
                text,score=max(alternatives,key=lambda item:item[1],default=("",0.0))
                if text:clipped_parts.append(text)
            if clipped_parts:result_parts.append(" ".join(clipped_parts))
        else:
            from .pattern_dsl import find_all
            alternatives=[]
            for lang in selected_languages:
                alternatives.extend(_run_rapidocr_candidates(crop,engine,lang,getattr(field,"pattern","") or ""))
            pattern=getattr(field,"pattern","") or ""
            alternatives.sort(key=lambda item:(bool(pattern and find_all(item[0],pattern)),item[1]),reverse=True)
            seen=set()
            for text,score in alternatives:
                text=str(text or "").strip()
                if text and text not in seen:
                    seen.add(text); result_parts.append(text)
        del crop,image,mask
        gc.collect()
        return result_parts
    except ImportError as exc: raise RuntimeError("OCR model/runtime is not installed") from exc
    except Exception as exc:
        _LOG.exception("OCR crop failed field=%s page=%s",getattr(field,"id",0),page_index+1)
        raise RuntimeError(f"OCR failed for field {getattr(field,'id',0)} on page {page_index+1}") from exc
