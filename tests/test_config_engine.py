from listorez2047.config import load_config, migrate_log_path


def test_removed_ocr_engines_migrate_to_rapidocr(monkeypatch, tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"engine":{"ocr_engine":"surya"}}', encoding="utf-8")
    monkeypatch.setattr("listorez2047.config.config_path", lambda: config)
    assert load_config()["engine"]["ocr_engine"] == "rapidocr"


def test_legacy_log_filename_is_renamed(tmp_path):
    old = tmp_path / "PDFOCRSplitter.log"
    assert migrate_log_path(old).endswith("Listorez2047.log")
    assert migrate_log_path(tmp_path / "notes.txt").endswith("notes.txt")


def test_load_config_migrates_legacy_log_path(monkeypatch, tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"log_path": "D:/PDFOCRsplitter/PDFOCRSplitter.log"}', encoding="utf-8")
    monkeypatch.setattr("listorez2047.config.config_path", lambda: config)
    assert load_config()["log_path"].endswith("Listorez2047.log")
