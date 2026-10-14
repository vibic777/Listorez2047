"""Field pattern DSL: typed positions + separator emit rules.

See TZ_RU.md §8. Pattern string is compiled to match (lenient separators)
and emit (canonical filename fragment).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Kind = Literal["D", "H", "h", "X", "M", "C", "U", "L", "A", "S", "class", "lit"]


@dataclass(frozen=True)
class DataSlot:
    kind: Kind
    width_min: int
    width_max: int  # -1 = unlimited
    charset: str = ""  # for class / lit
    pad: bool = False
    strict_case: bool = False


@dataclass(frozen=True)
class SepSlot:
    emit: str
    mode: Literal["flex", "strict", "delete"]
    strict_set: str = ""


@dataclass(frozen=True)
class AnchorSlot:
    alternatives: tuple[str, ...]


Slot = DataSlot | SepSlot | AnchorSlot

_FLEX_PUNCT = set(".,:;/-–—·•|_")
_TOKEN = set("DHhXMCASUL")
_MAX_SEP = 8

_D_CLASS = r"[0-9OoОоIl|]"
_H_CLASS = r"[0-9A-Fa-fOo]"
_C_CLASS = r"[^\W\d_]|[ЁёА-Яа-я]"  # letters; fallback below
_C_CLASS = r"[A-Za-zА-Яа-яЁё\u0400-\u04FF\u4E00-\u9FFF]"
_S_CLASS = r"[\-+=.,]"
_MONTH_WORD = (
    r"(?:(?:январ|янв|феврал|фев|март|апрел|апр|июн|июл|август|авг|"
    r"сентябр|сент|сен|октябр|окт|ноябр|ноя|декабр|дек)[А-Яа-яЁё]*|"
    r"май|мая|мае|january|jan|february|feb|march|mar|april|apr|may|"
    r"june|jun|july|jul|august|aug|september|sep|october|oct|"
    r"november|nov|december|dec)\.?(?![A-Za-zА-Яа-яЁё])"
)
_MONTH_PREFIXES = (
    (("январ", "янв", "january", "jan"), 1), (("феврал", "фев", "february", "feb"), 2),
    (("март", "march", "mar"), 3), (("апрел", "апр", "april", "apr"), 4),
    (("май", "мая", "мае", "may"), 5), (("июн", "june", "jun"), 6),
    (("июл", "july", "jul"), 7), (("август", "авг", "august", "aug"), 8),
    (("сентябр", "сент", "сен", "september", "sep"), 9),
    (("октябр", "окт", "october", "oct"), 10), (("ноябр", "ноя", "november", "nov"), 11),
    (("декабр", "дек", "december", "dec"), 12),
)


def _read_quant(pattern: str, i: int) -> tuple[int, int, int, bool]:
    if i >= len(pattern):
        return 1, 1, i, False
    ch = pattern[i]
    if ch == "+":
        return 1, -1, i + 1, True
    if ch == "*":
        return 0, -1, i + 1, True
    if ch == "?":
        return 0, 1, i + 1, True
    if ch == "{" and i + 1 < len(pattern) and pattern[i + 1].isdigit():
        m = re.match(r"\{(\d+)(?:\s*,\s*(\d+))?\}", pattern[i:])
        if m:
            a = int(m.group(1))
            b = int(m.group(2)) if m.group(2) is not None else a
            return a, b, i + m.end(), True
    return 1, 1, i, False


def _parse_brackets(body: str) -> SepSlot:
    raw = body.strip()
    emit = ""
    mode: Literal["flex", "strict", "delete"] = "flex"
    strict_set = ""

    if r"\c=" in raw:
        left, _, right = raw.partition(r"\c=")
        emit = right[:1] if right else ""
        mode = "flex"
        return SepSlot(emit=emit, mode=mode)
    if raw.endswith(r"\d") or raw.endswith("\\d"):
        return SepSlot(emit="", mode="delete")
    if ">" in raw:
        left, _, right = raw.partition(">")
        emit = right
        left = left.strip()
        if left in {"*", ".*", "*?", ".*?"}:
            mode = "delete" if emit == "" else "flex"
        elif left.startswith("!"):
            mode = "strict"
            strict_set = left[1:]
        else:
            mode = "strict" if left and left not in "*." else "flex"
            if mode == "strict":
                strict_set = left.replace(".", ".")
                if not strict_set:
                    strict_set = "."
            emit = right
        if emit == "" and mode != "strict":
            mode = "delete"
        return SepSlot(emit=emit, mode=mode, strict_set=strict_set)
    if raw in {"*", ".*", "*?"}:
        return SepSlot(emit="", mode="delete")
    return SepSlot(emit=raw, mode="flex")


def parse(pattern: str) -> list[Slot]:
    slots: list[Slot] = []
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "@" and pattern.startswith("@{", i):
            j=pattern.find("}",i+2)
            if j<0:raise ValueError("unclosed @{ anchor")
            alternatives=tuple(dict.fromkeys(part.strip() for part in pattern[i+2:j].split("|") if part.strip()))
            if not alternatives:raise ValueError("empty @{ anchor")
            # The printed number sign is often transcribed as one of these
            # equivalent strings by OCR. Anchors are context only, never output.
            if alternatives==("№",):alternatives=("№","No","Nº","N°")
            slots.append(AnchorSlot(alternatives)); i=j+1; continue
        if ch == "[":
            j = pattern.find("]", i + 1)
            if j < 0:
                raise ValueError("unclosed [ in pattern")
            slots.append(_parse_brackets(pattern[i + 1 : j]))
            i = j + 1
            continue
        if ch == "{":
            j = pattern.find("}", i + 1)
            if j < 0:
                raise ValueError("unclosed { in pattern")
            body = pattern[i + 1 : j]
            i = j + 1
            mn, mx, i, explicit = _read_quant(pattern, i)
            if not explicit:
                mn, mx = 1, -1
            slots.append(DataSlot("class", mn, mx, charset=body))
            continue
        if ch == "\\":
            if i + 1 >= n:
                break
            lit = pattern[i + 1]
            i += 2
            mn, mx, i, _explicit = _read_quant(pattern, i)
            slots.append(DataSlot("lit", mn, mx, charset=lit))
            continue
        if ch in _TOKEN:
            kind = ch  # type: ignore[assignment]
            i += 1
            if kind == "M":
                # MM is syntactic sugar for one calendar-month slot.
                if i < n and pattern[i] == "M":
                    i += 1
                slots.append(DataSlot("M", 1, 1))
                continue
            strict_case = False
            if i < n and pattern[i] == "!":
                strict_case = True
                i += 1
            mn, mx, i, explicit = _read_quant(pattern, i)
            # Padding belongs only to adjacent drawn positions (DD, HHH), never
            # to an explicitly quantified variable-length slot such as D{1,4}.
            pad = kind in {"D", "H", "h", "X"} and not explicit
            slots.append(
                DataSlot(kind, mn, mx, pad=pad, strict_case=strict_case)  # type: ignore[arg-type]
            )
            continue
        if ch in ". ,:;/-":
            emit = ch if ch != " " else " "
            slots.append(SepSlot(emit=emit, mode="flex"))
            i += 1
            continue
        slots.append(DataSlot("lit", 1, 1, charset=ch))
        i += 1

    return _merge_runs(slots)


def _merge_runs(slots: list[Slot]) -> list[Slot]:
    out: list[Slot] = []
    for slot in slots:
        if (
            out
            and isinstance(slot, DataSlot)
            and isinstance(out[-1], DataSlot)
            and slot.kind == out[-1].kind
                and slot.kind in {"D", "H", "h", "X", "U", "L"}
            and slot.width_min == slot.width_max == 1
            and out[-1].width_max >= 1
        ):
            prev = out[-1]
            out[-1] = DataSlot(
                prev.kind,
                1,
                prev.width_max + 1,
                pad=True,
                strict_case=prev.strict_case,
            )
        else:
            out.append(slot)
    return out


def _data_regex(slot: DataSlot) -> str:
    if slot.kind == "D":
        unit = _D_CLASS
    elif slot.kind in {"H", "h", "X"}:
        if slot.strict_case and slot.kind == "H":
            unit = r"[0-9A-FO]"
        elif slot.strict_case and slot.kind == "h":
            unit = r"[0-9a-fo]"
        else:
            unit = _H_CLASS
    elif slot.kind in {"C", "U", "L"}:
        if slot.strict_case and slot.kind == "U":
            unit = r"[A-ZА-ЯЁ\u4E00-\u9FFF]"
        elif slot.strict_case and slot.kind == "L":
            unit = r"[a-zа-яё]"
        else:
            unit = _C_CLASS
    elif slot.kind == "A":
        unit = r"[^\r\n]"
    elif slot.kind == "S":
        unit = _S_CLASS
    elif slot.kind == "M":
        numeric = r"(?:[1-9Il|]|[0OoОо][1-9Il|]|[1Il|][0-2OoОоIl|])"
        return rf"(?:(?<![0-9OoОоIl|]){numeric}(?![0-9OoОоIl|])|(?i:{_MONTH_WORD}))"
    elif slot.kind == "class":
        unit = "[" + slot.charset.replace("]", r"\]") + "]"
    else:
        unit = re.escape(slot.charset)
    mn, mx = slot.width_min, slot.width_max
    if slot.pad and slot.kind in {"D", "H", "h", "X"} and mx >= 1:
        mn = 1
    return unit + _quant(mn, mx)


def _quant(mn: int, mx: int) -> str:
    if mn == 1 and mx == 1:
        return ""
    if mn == 0 and mx == 1:
        return "?"
    if mn == 1 and mx == -1:
        return "+"
    if mn == 0 and mx == -1:
        return "*"
    if mx == -1:
        return f"{{{mn},}}"
    if mn == mx:
        return f"{{{mn}}}"
    return f"{{{mn},{mx}}}"


def _next_data_kind(slots: list[Slot], index: int) -> Kind | None:
    for slot in slots[index + 1 :]:
        if isinstance(slot, DataSlot):
            return slot.kind
    return None


def _sep_regex(slot: SepSlot, next_kind: Kind | None) -> str:
    if slot.mode == "strict":
        charset = slot.strict_set or slot.emit or "."
        return "[" + re.escape(charset) + "]"
    if next_kind == "M":
        # A month may start with a digit or a letter. Keep the separator lazy so
        # it cannot steal the end of the day or a prefix of the month itself.
        skip = r".{0,%d}?" % _MAX_SEP
    elif next_kind == "D":
        skip = r"[^0-9OoОоIl|]{0,%d}" % _MAX_SEP
    elif next_kind in {"H", "h", "X"}:
        skip = r"[^0-9A-Fa-fOo]{0,%d}" % _MAX_SEP
    elif next_kind == "C":
        skip = r"[^A-Za-zА-Яа-яЁё\u4E00-\u9FFF]{0,%d}" % _MAX_SEP
    else:
        skip = r".{0,%d}" % _MAX_SEP
    return skip


def _map_digit(chunk: str) -> str:
    table = str.maketrans(
        {
            "O": "0",
            "o": "0",
            "О": "0",
            "о": "0",
            "I": "1",
            "l": "1",
            "|": "1",
        }
    )
    # str.isdigit() also accepts characters such as ² that int() cannot parse.
    # OCR output is untrusted, so keep the numeric DSL strictly ASCII-safe.
    return "".join(ch for ch in chunk.translate(table) if ch in "0123456789")


def _map_hex(chunk: str, case: str) -> str:
    table = str.maketrans({"O": "0", "o": "0"})
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", chunk.translate(table))
    if case == "upper":
        return cleaned.upper()
    if case == "lower":
        return cleaned.lower()
    return cleaned


def _map_month(chunk: str) -> str:
    word = chunk.casefold().rstrip(".")
    for prefixes, value in _MONTH_PREFIXES:
        if any(word.startswith(prefix) for prefix in prefixes):
            return f"{value:02d}"
    digits = _map_digit(chunk)
    if digits:
        try:value = int(digits)
        except ValueError:return ""
        return f"{value:02d}" if 1 <= value <= 12 else ""
    return ""


def compile_pattern(pattern: str) -> re.Pattern[str]:
    slots = parse(pattern)
    parts: list[str] = []
    for idx, slot in enumerate(slots):
        if isinstance(slot, AnchorSlot):
            alternatives=[]
            for value in slot.alternatives:
                escaped=re.escape(value)
                if value in {"No","Nº","N°"}:
                    escaped=rf"(?<![A-Za-z]){escaped}(?![A-Za-z])"
                alternatives.append(escaped)
            parts.append(r".*?(?:"+"|".join(alternatives)+r").*?")
        elif isinstance(slot, SepSlot):
            parts.append(f"(?P<s{idx}>" + _sep_regex(slot, _next_data_kind(slots, idx)) + ")")
        else:
            parts.append(f"(?P<d{idx}>" + _data_regex(slot) + ")")
    return re.compile("".join(parts))


def pattern_issue(pattern: str) -> str | None:
    """counter if this is a filename formula; invalid if it cannot compile; else None."""
    raw=str(pattern or "").strip()
    if not raw:return None
    from .naming import is_counter_template
    if is_counter_template(raw):return "counter"
    try:
        compile_pattern(raw)
    except (ValueError, re.error, OverflowError, TypeError):
        return "invalid"
    return None


def find_all(text: str, pattern: str) -> list[str]:
    if not pattern:return []
    try:
        rx = compile_pattern(pattern)
    except (ValueError, re.error, OverflowError, TypeError):
        return []
    found: list[str] = []
    source=str(text or "")
    slots=parse(pattern)
    digit_groups=[f"d{i}" for i,slot in enumerate(slots) if isinstance(slot,DataSlot) and slot.kind=="D"]
    try:
        for match in rx.finditer(source):
            # D intentionally maps OCR confusions such as O→0 and I→1, but
            # must not extract the 'o' from a word like "No" (a common OCR
            # rendering of the printed № sign) as a standalone zero.
            raw="".join(match.group(name) or "" for name in digit_groups)
            spans=[match.span(name) for name in digit_groups if match.group(name)]
            if raw and all(ch in "OoОоIl|" for ch in raw) and not any(ch.isdigit() for ch in raw) and spans:
                start=min(span[0] for span in spans); end=max(span[1] for span in spans)
                if (start>0 and source[start-1].isalpha()) or (end<len(source) and source[end].isalpha()):
                    continue
            emitted = emit_match(pattern, match)
            if emitted:
                found.append(emitted)
    except (ValueError, re.error, OverflowError):
        return []
    return found


def emit_match(pattern: str, match: re.Match[str]) -> str:
    slots = parse(pattern)
    out: list[str] = []
    for idx, slot in enumerate(slots):
        if isinstance(slot,AnchorSlot):
            continue
        if isinstance(slot, SepSlot):
            if slot.mode == "delete":
                continue
            out.append(slot.emit)
            continue
        raw = match.group(f"d{idx}") or ""
        if slot.kind == "D":
            digits = _map_digit(raw)
            width = slot.width_max if slot.width_max > 0 else slot.width_min
            if slot.pad and width > 0:
                digits = digits.zfill(width)
            out.append(digits)
        elif slot.kind == "M":
            month = _map_month(raw)
            if not month:
                return ""
            out.append(month)
        elif slot.kind == "H":
            hx = _map_hex(raw, "upper")
            width = slot.width_max if slot.width_max > 0 else slot.width_min
            if slot.pad and width > 0:
                hx = hx.zfill(width).upper()
            out.append(hx)
        elif slot.kind == "h":
            hx = _map_hex(raw, "lower")
            width = slot.width_max if slot.width_max > 0 else slot.width_min
            if slot.pad and width > 0:
                hx = hx.zfill(width).lower()
            out.append(hx)
        elif slot.kind == "X":
            hx = _map_hex(raw, "keep")
            width = slot.width_max if slot.width_max > 0 else slot.width_min
            if slot.pad and width > 0:
                hx = hx.zfill(width)
            out.append(hx)
        elif slot.kind == "U":
            out.append(raw.upper())
        elif slot.kind == "L":
            out.append(raw.lower())
        else:
            out.append(raw)
    return "".join(out)


def normalize(text: str, pattern: str) -> str | None:
    hits = find_all(text, pattern)
    if not hits:
        return None
    return hits[0]
