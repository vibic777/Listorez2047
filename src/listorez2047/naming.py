"""Filename template: field placeholders and page counters."""

from __future__ import annotations

import re
from typing import Mapping

_COUNTER = re.compile(r"\{(-?\d+)\s*:\s*([+\-*%])\s*(-?\d+)(#)?\}")
_FIELD = re.compile(r"\{(\d+)\}")
_WIN_BAD = re.compile(r'[\\/:*?"<>|]')
_MAX_DIGITS = 18


def counter_value(start: int, op: str, operand: int, page_index: int) -> int | None:
    """page_index is 0-based in the open PDF. None means forbidden or overflow."""
    try:
        i = int(page_index)
        start=int(start); operand=int(operand)
    except (TypeError,ValueError):
        return None
    if i<0:i=0
    try:
        if op == "+":
            return start + i * operand
        if op == "-":
            return start - i * operand
        if op == "*":
            if i == 0:
                return start
            if operand == 0:
                return 0
            if i > 30 or abs(operand) > 100:
                return None
            value = start * (operand**i)
            if len(str(abs(value))) > _MAX_DIGITS:
                return None
            return value
        if op == "%":
            if operand == 0:
                return None
            return (start + i) % operand
    except (OverflowError, MemoryError, ValueError):
        return None
    return None


def _format_int(value: int) -> str:
    text = str(value)
    if len(text.lstrip("-")) > _MAX_DIGITS:
        return "overflow"
    return text


def expand_template(
    template: str,
    fields: Mapping[int, str],
    page_index: int,
    save_index: int = 0,
) -> str:
    """Replace counters then {n} field slots.

    page_index: 0 = first page of the open PDF.
    save_index: 0 = next file to save in this session (increments only after a successful save).
    Suffix # on a counter uses save_index, otherwise page_index.
    """

    def replace_counter(match: re.Match[str]) -> str:
        start = int(match.group(1))
        op = match.group(2)
        operand = int(match.group(3))
        by_save = match.group(4) == "#"
        index = save_index if by_save else page_index
        value = counter_value(start, op, operand, index)
        if value is None:
            return ""
        return _format_int(value)

    def replace_field(match: re.Match[str]) -> str:
        number = int(match.group(1))
        return str(fields.get(number, "") or "")

    text = _COUNTER.sub(replace_counter, str(template or ""))
    return _FIELD.sub(replace_field, text)


def is_counter_template(text: str) -> bool:
    """True if the whole string is a filename counter such as {235:+1} or {505:+1#}."""
    return bool(text and _COUNTER.fullmatch(str(text).strip()))


def expression_issue(text: str) -> str | None:
    """empty / invalid if the default is not a usable expression. None if OK."""
    raw=str(text or "").strip()
    if not raw:return "empty"
    leftover=_COUNTER.sub("",raw)
    leftover=_FIELD.sub("",leftover)
    if "{" in leftover or "}" in leftover:return "invalid"
    return None


def expand_template_safe(template: str, fields: Mapping[int, str], page_index: int, save_index: int = 0) -> str:
    try:
        return expand_template(template,fields,page_index,save_index)
    except (TypeError,ValueError,OverflowError,MemoryError,re.error):
        return ""


def build_filename(template: str, fields: Mapping[int, str], page_index: int, save_index: int = 0) -> str:
    """Expand the template and return a Windows-safe `.pdf` name for this page."""
    return sanitize_filename(expand_template_safe(template, fields, page_index, save_index), page_index + 1) + ".pdf"

def sanitize_filename(name: str, page_number_1based: int) -> str:
    stem = _WIN_BAD.sub("_", name).strip().rstrip(".")
    if not stem:
        stem = f"page_{page_number_1based}"
    if len(stem) > 150:
        stem = stem[:150].rstrip(". ")
    return stem
