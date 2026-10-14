"""Entry point: python -m listorez2047"""

from __future__ import annotations

import sys
import argparse
from listorez2047 import __version__


def build_parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(
        prog="Listorez2047",
        description="Offline PDF splitter. OCR (RapidOCR/PP-OCRv5, CPU only) is used to build filenames; each output PDF is a copy of one source page.",
        epilog="Run without options to open the desktop interface.",
    )
    parser.add_argument("--version",action="version",version=f"%(prog)s {__version__}")
    return parser


def main() -> int:
    build_parser().parse_args()
    from PySide6.QtWidgets import QApplication
    from listorez2047.app_logging import setup_logging,log_exception,log_unraisable,install_qt_logging,LOGGER
    from listorez2047.config import load_config
    setup_logging(load_config()); sys.excepthook=log_exception
    if hasattr(sys,"unraisablehook"):sys.unraisablehook=log_unraisable
    # Initialize the log before importing the full UI/OCR graph so packaging
    # failures are recorded instead of closing a windowed build silently.
    from listorez2047.main_window import MainWindow
    app=QApplication(sys.argv); app.setApplicationName("Listorez2047")
    install_qt_logging(app)
    LOGGER.info("UI starting")
    window=MainWindow(); window.show()
    LOGGER.info("Main window shown")
    code=app.exec()
    LOGGER.info("Application exit code=%s",code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
