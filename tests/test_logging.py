import logging
from listorez2047.app_logging import setup_logging, LOGGER, TRACE_LEVEL, normalize_log_levels
from listorez2047.config import default_log_path, load_config


def test_setup_logging_writes_all_levels(tmp_path):
    log = tmp_path / "Listorez2047.log"
    setup_logging({"logging_enabled": True, "log_path": str(log), "log_levels": normalize_log_levels(None)})
    LOGGER.log(TRACE_LEVEL, "trace-point")
    LOGGER.debug("debug-point")
    LOGGER.info("info-point")
    LOGGER.warning("warning-point")
    LOGGER.error("error-point")
    LOGGER.critical("critical-point")
    text = log.read_text(encoding="utf-8")
    for token in ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "debug-point", "critical-point", "trace-point"):
        assert token in text


def test_log_level_filter_drops_unchecked_levels(tmp_path):
    log = tmp_path / "filtered.log"
    levels = normalize_log_levels(None)
    levels["debug"] = False
    levels["info"] = False
    levels["trace"] = False
    setup_logging({"logging_enabled": True, "log_path": str(log), "log_levels": levels})
    LOGGER.debug("hidden-debug")
    LOGGER.info("hidden-info")
    LOGGER.error("visible-error")
    text = log.read_text(encoding="utf-8")
    assert "visible-error" in text
    assert "hidden-debug" not in text
    assert "hidden-info" not in text


def test_logging_can_be_disabled(tmp_path):
    log = tmp_path / "silent.log"
    setup_logging({"logging_enabled": False, "log_path": str(log)})
    LOGGER.critical("should-not-appear")
    assert not log.exists()
    logging.disable(logging.NOTSET)


def test_default_log_path_is_writable_location():
    path = default_log_path()
    assert path.name == "Listorez2047.log"
    assert path.parent.name in {"Listorez2047", path.parent.name}


def test_load_config_logging_defaults_off(monkeypatch, tmp_path):
    config = tmp_path / "config.json"
    monkeypatch.setattr("listorez2047.config.config_path", lambda: config)
    data = load_config()
    assert data["logging_enabled"] is False
    assert data["log_path"].endswith("Listorez2047.log")
    assert data["log_levels"]["error"] is True
    assert data["log_levels"]["trace"] is True
    assert data["engine"]["auto_deskew"] is True
