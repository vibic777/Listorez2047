from listorez2047 import ocr_engine


def image_stub():
    return type("ImageShape", (), {"shape": (50, 120, 3)})()


def test_weak_read_keeps_pattern_matching_alternatives_first(monkeypatch):
    reads = iter(
        [
            ("№ 0", 0.60),
            ("№ 216", 0.72),
            ("№ 216", 0.70),
            ("unrelated", 0.95),
        ]
    )
    monkeypatch.setattr(ocr_engine, "_run_rapidocr", lambda *_args: next(reads))
    monkeypatch.setattr(ocr_engine, "_handwriting_variant", lambda _image, _kind: object())

    candidates = ocr_engine._run_rapidocr_candidates(
        image_stub(), {"drop_score": 0.5}, "eslav", "@{№}D{1,4}"
    )

    assert candidates == [("№ 216", 0.72), ("№ 0", 0.60), ("unrelated", 0.95)]


def test_confident_pattern_match_skips_retry(monkeypatch):
    calls = []

    def run(*_args):
        calls.append(True)
        return "№ 216", 0.90

    monkeypatch.setattr(ocr_engine, "_run_rapidocr", run)
    monkeypatch.setattr(
        ocr_engine,
        "_handwriting_variant",
        lambda *_args: (_ for _ in ()).throw(AssertionError("unexpected retry")),
    )

    candidates = ocr_engine._run_rapidocr_candidates(
        image_stub(), {"drop_score": 0.5}, "eslav", "@{№}D{1,4}"
    )

    assert candidates == [("№ 216", 0.90)]
    assert len(calls) == 1


def test_wide_numeric_field_retries_confident_single_digit(monkeypatch):
    reads = iter(
        [
            ("№ 0", 0.95),
            ("№ 216", 0.75),
            ("№ 216", 0.74),
            ("№ 0", 0.80),
        ]
    )
    monkeypatch.setattr(ocr_engine, "_run_rapidocr", lambda *_args: next(reads))
    monkeypatch.setattr(ocr_engine, "_handwriting_variant", lambda _image, _kind: object())
    candidates = ocr_engine._run_rapidocr_candidates(
        image_stub(), {"drop_score": 0.5}, "eslav", "@{№}D{1,4}"
    )

    assert candidates == [("№ 0", 0.95), ("№ 216", 0.75)]
