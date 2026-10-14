from __future__ import annotations
import faulthandler,logging,os,sys,traceback
from pathlib import Path

_fault_file=None
LOGGER=logging.getLogger("listorez2047")
TRACE_LEVEL=5
logging.addLevelName(TRACE_LEVEL,"TRACE")
LOG_LEVEL_NAMES=("trace","debug","info","warning","error","critical")
_LEVEL_BY_NAME={
    "trace":TRACE_LEVEL,
    "debug":logging.DEBUG,
    "info":logging.INFO,
    "warning":logging.WARNING,
    "error":logging.ERROR,
    "critical":logging.CRITICAL,
}

class FlushingFileHandler(logging.FileHandler):
    def emit(self,record):
        super().emit(record)
        self.flush()

class LevelNameFilter(logging.Filter):
    """Keep only selected named levels (trace/debug/info/warning/error/critical)."""
    def __init__(self,enabled:dict|None=None):
        super().__init__()
        self.enabled={name for name,on in (enabled or {}).items() if on}

    def filter(self,record):
        name=record.levelname.lower()
        if name=="warn":name="warning"
        if name=="fatal":name="critical"
        return name in self.enabled

def default_log_path()->Path:
    if getattr(sys,"frozen",False):
        return Path(sys.executable).resolve().parent/"Listorez2047.log"
    return Path(os.environ.get("APPDATA",Path.home()/".config"))/"Listorez2047"/"Listorez2047.log"

def default_log_levels()->dict:
    return {name:True for name in LOG_LEVEL_NAMES}

def normalize_log_levels(raw)->dict:
    levels=default_log_levels()
    if isinstance(raw,dict):
        for name in LOG_LEVEL_NAMES:
            if name in raw:levels[name]=bool(raw[name])
    return levels

def setup_logging(config:dict)->Path|None:
    global _fault_file
    if not config.get("logging_enabled",False):
        logging.disable(logging.CRITICAL)
        return None
    path=Path(config.get("log_path") or default_log_path())
    path.parent.mkdir(parents=True,exist_ok=True)
    logging.disable(logging.NOTSET)
    levels=normalize_log_levels(config.get("log_levels"))
    enabled_nums=[_LEVEL_BY_NAME[name] for name,on in levels.items() if on]
    if not enabled_nums:
        logging.disable(logging.CRITICAL)
        return None
    handler=FlushingFileHandler(path,encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(LevelNameFilter(levels))
    root=logging.getLogger()
    root.handlers.clear()
    root.setLevel(min(enabled_nums))
    root.addHandler(handler)
    LOGGER.setLevel(min(enabled_nums))
    LOGGER.log(logging.INFO if levels.get("info") else min(enabled_nums),"Listorez2047 started log=%s levels=%s",path,",".join(n for n,on in levels.items() if on))
    try:
        if _fault_file:
            try:_fault_file.close()
            except OSError:pass
        _fault_file=path.open("a",encoding="utf-8")
        faulthandler.enable(_fault_file,all_threads=True)
    except (OSError,RuntimeError):
        LOGGER.exception("Could not enable faulthandler")
    return path

def log_exception(exc_type,exc_value,exc_tb):
    LOGGER.critical("Unhandled exception",exc_info=(exc_type,exc_value,exc_tb))
    traceback.print_exception(exc_type,exc_value,exc_tb)

def log_unraisable(hook_args):
    LOGGER.critical("Unraisable exception in %s",getattr(hook_args,"object",None),exc_info=(hook_args.exc_type,hook_args.exc_value,hook_args.exc_traceback))

def install_qt_logging(app=None):
    try:
        from PySide6.QtCore import QtMsgType,qInstallMessageHandler
    except Exception:
        LOGGER.exception("Qt logging is unavailable")
        return
    levels={QtMsgType.QtDebugMsg:logging.DEBUG,QtMsgType.QtInfoMsg:logging.INFO,QtMsgType.QtWarningMsg:logging.WARNING,QtMsgType.QtCriticalMsg:logging.ERROR,QtMsgType.QtFatalMsg:logging.CRITICAL}
    def handler(mode,context,message):
        LOGGER.log(levels.get(mode,logging.WARNING),"Qt %s:%s %s",getattr(context,"file",""),getattr(context,"line",0),message)
    qInstallMessageHandler(handler)
    if app is None:return
    original=app.notify
    def notify(receiver,event):
        try:
            return original(receiver,event)
        except Exception:
            LOGGER.critical("Unhandled Qt event receiver=%s event=%s",type(receiver).__name__,type(event).__name__,exc_info=True)
            return False
    app.notify=notify
