"""Skins and window icons. Colors live in skins.json, not in widgets."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_DIR = Path(__file__).resolve().parent
_CATALOG_PATH = _DIR / "skins.json"


def _icons_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / "icons"
    return Path(__file__).resolve().parents[3] / "assets" / "icons"


def load_catalog() -> dict[str, Any]:
    with _CATALOG_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def skin_by_id(skin_id: str) -> dict[str, Any]:
    catalog = load_catalog()
    for item in catalog["skins"]:
        if item["id"] == skin_id:
            return item
    default = catalog.get("default_skin", "it_gray")
    for item in catalog["skins"]:
        if item["id"] == default:
            return item
    return catalog["skins"][0]


def icon_path(icon_id: str) -> Path:
    catalog = load_catalog()
    filename = "it.png"
    for item in catalog["icons"]:
        if item["id"] == icon_id:
            filename = item["file"]
            break
    return _icons_dir() / filename


def default_icon_for_skin(skin_id: str) -> str:
    catalog = load_catalog()
    mapping = catalog.get("skin_default_icon") or {}
    return str(mapping.get(skin_id) or catalog.get("default_icon") or "it")


def qss_for_skin(skin: dict[str, Any]) -> str:
    """Qt stylesheet from palette tokens. Keep widgets free of hardcoded colors."""
    return f"""
    QWidget {{
        background-color: {skin["window"]};
        color: {skin["text"]};
    }}
    QMainWindow, QDialog, QMenuBar, QMenu, QStatusBar {{
        background-color: {skin["window"]};
        color: {skin["text"]};
    }}
    QMenuBar::item:selected, QMenu::item:selected {{
        background-color: {skin["panel_alt"]};
    }}
    QFrame, QGroupBox, QTabWidget::pane {{
        background-color: {skin["panel"]};
        border: 1px solid {skin["border"]};
        color: {skin["text"]};
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {skin["input"]};
        color: {skin["text"]};
        border: 1px solid {skin["border"]};
        selection-background-color: {skin["accent"]};
        selection-color: {skin["accent_text"]};
    }}
    QPushButton {{
        background-color: {skin["button"]};
        color: {skin["text"]};
        border: 1px solid {skin["border"]};
        padding: 4px 10px;
    }}
    QPushButton:hover {{
        background-color: {skin["button_hover"]};
    }}
    QPushButton:default, QPushButton[primary="true"] {{
        background-color: {skin["accent"]};
        color: {skin["accent_text"]};
    }}
    QListWidget, QTreeWidget, QTableView {{
        background-color: {skin["panel"]};
        color: {skin["text"]};
        alternate-background-color: {skin["panel_alt"]};
        border: 1px solid {skin["border"]};
    }}
    QScrollBar:vertical, QScrollBar:horizontal {{
        background: {skin["panel"]};
        border: none;
    }}
    QLabel[muted="true"] {{
        color: {skin["text_muted"]};
    }}
    QCheckBox::indicator {{
        width: 17px; height: 17px;
        background-color: {skin["input"]};
        border: 2px solid {skin["text"]};
    }}
    QCheckBox::indicator:checked {{
        background-color: {skin["accent"]};
        border: 3px solid {skin["text"]};
    }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        width: 24px;
        subcontrol-origin: border;
        subcontrol-position: top right;
        background-color: {skin["panel_alt"]};
        border: 1px solid {skin["text"]};
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        width: 24px;
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        background-color: {skin["panel_alt"]};
        border: 1px solid {skin["text"]};
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover,
    QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {skin["accent"]};
    }}
    """
