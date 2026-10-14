"""Effective OCR region when field rectangles overlap (TZ §7.12)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

OverlapMode = Literal["recognize", "clip"]


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    def is_empty(self, eps: float = 1e-12) -> bool:
        return self.w <= eps or self.h <= eps


def _overlap(a: Rect, b: Rect) -> Rect | None:
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return Rect(x1, y1, x2 - x1, y2 - y1)


def subtract_rect(a: Rect, hole: Rect) -> list[Rect]:
    """Cover `a` minus `hole` with axis-aligned pieces (0–4 rectangles)."""
    inter = _overlap(a, hole)
    if inter is None or a.is_empty():
        return [] if a.is_empty() else [a]
    pieces: list[Rect] = []
    if inter.y > a.y:
        pieces.append(Rect(a.x, a.y, a.w, inter.y - a.y))
    if a.y2 > inter.y2:
        pieces.append(Rect(a.x, inter.y2, a.w, a.y2 - inter.y2))
    if inter.x > a.x:
        pieces.append(Rect(a.x, inter.y, inter.x - a.x, inter.h))
    if a.x2 > inter.x2:
        pieces.append(Rect(inter.x2, inter.y, a.x2 - inter.x2, inter.h))
    return [p for p in pieces if not p.is_empty()]


def subtract_many(a: Rect, holes: Iterable[Rect]) -> list[Rect]:
    remaining = [a]
    for hole in holes:
        nxt: list[Rect] = []
        for piece in remaining:
            nxt.extend(subtract_rect(piece, hole))
        remaining = nxt
        if not remaining:
            break
    return remaining


def effective_rects(
    field: Rect,
    others: Sequence[Rect],
    mode: OverlapMode = "recognize",
) -> list[Rect]:
    """Region used for OCR / native text of this field."""
    if mode != "clip":
        return [] if field.is_empty() else [field]
    return subtract_many(field, others)
