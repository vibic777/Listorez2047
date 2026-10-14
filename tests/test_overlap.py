from listorez2047.overlap import Rect, effective_rects, subtract_rect


def test_recognize_keeps_full_rect():
    a = Rect(0.0, 0.0, 0.5, 0.5)
    b = Rect(0.25, 0.25, 0.5, 0.5)
    assert effective_rects(a, [b], "recognize") == [a]


def test_clip_subtracts_other_field():
    a = Rect(0.0, 0.0, 1.0, 0.4)
    b = Rect(0.5, 0.0, 0.5, 0.4)
    left = effective_rects(a, [b], "clip")
    assert len(left) == 1
    assert left[0].x == 0.0
    assert abs(left[0].w - 0.5) < 1e-9


def test_both_clip_share_nothing():
    a = Rect(0.0, 0.0, 0.6, 0.4)
    b = Rect(0.4, 0.0, 0.6, 0.4)
    a_parts = effective_rects(a, [b], "clip")
    b_parts = effective_rects(b, [a], "clip")
    assert abs(sum(p.w * p.h for p in a_parts) - 0.16) < 1e-9
    assert abs(sum(p.w * p.h for p in b_parts) - 0.16) < 1e-9


def test_fully_covered_is_empty():
    a = Rect(0.1, 0.1, 0.2, 0.2)
    b = Rect(0.0, 0.0, 1.0, 1.0)
    assert effective_rects(a, [b], "clip") == []


def test_no_overlap_clip_equals_recognize():
    a = Rect(0.0, 0.0, 0.2, 0.2)
    b = Rect(0.5, 0.5, 0.2, 0.2)
    assert effective_rects(a, [b], "clip") == [a]


def test_subtract_l_shape():
    outer = Rect(0.0, 0.0, 1.0, 1.0)
    inner = Rect(0.5, 0.0, 0.5, 0.5)
    pieces = subtract_rect(outer, inner)
    area = sum(p.w * p.h for p in pieces)
    assert abs(area - 0.75) < 1e-9
