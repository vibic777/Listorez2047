"""Interface language dictionary.

Add a language: drop locales/<code>.json and a row in locales/languages.json.
"""

from __future__ import annotations

import json
import locale
from pathlib import Path
from typing import Any

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def available_languages() -> list[dict[str, str]]:
    catalog = _load_json(_LOCALES_DIR / "languages.json")
    return list(catalog.get("languages", []))


def default_language_code() -> str:
    catalog = _load_json(_LOCALES_DIR / "languages.json")
    return str(catalog.get("default") or "ru")


def detect_os_language() -> str:
    codes = {item["code"] for item in available_languages()}
    try:
        os_locale, _enc = locale.getlocale()
    except (TypeError, ValueError):
        os_locale = None
    if os_locale:
        short = os_locale.replace("-", "_").split("_")[0].lower()
        if short in codes:
            return short
    return default_language_code()


class I18n:
    def __init__(self, language: str | None = None) -> None:
        self._strings: dict[str, str] = {}
        self._fallback: dict[str, str] = {}
        self.language = language or detect_os_language()
        self.load(self.language)

    def load(self, language: str) -> None:
        codes = {item["code"] for item in available_languages()}
        if language not in codes:
            language = default_language_code()
        self.language = language
        fallback_code = default_language_code()
        self._fallback = _load_json(_LOCALES_DIR / f"{fallback_code}.json")
        path = _LOCALES_DIR / f"{language}.json"
        self._strings = _load_json(path) if path.exists() else dict(self._fallback)

    def t(self, key: str, **kwargs: Any) -> str:
        raw = self._strings.get(key) or self._fallback.get(key) or key
        if kwargs:
            try:
                return raw.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return raw
        return raw


_i18n: I18n | None = None


def get_i18n() -> I18n:
    global _i18n
    if _i18n is None:
        _i18n = I18n()
    return _i18n


def t(key: str, **kwargs: Any) -> str:
    return get_i18n().t(key, **kwargs)


def set_language(language: str) -> None:
    get_i18n().load(language)
