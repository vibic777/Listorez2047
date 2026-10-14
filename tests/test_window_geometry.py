from listorez2047.config import (clamp_geometry, load_config, remember_geometry,
                                    reset_geometries, stored_geometry, valid_preprocess_strategy)


def test_session_geometry_is_remembered_and_reset():
    store = {}
    remember_geometry(store, "review", 100, 80, 400, 300)
    remember_geometry(store, "auto_progress", 40, 50, 360, 180)
    assert stored_geometry(store, "review") == {"x": 100, "y": 80, "w": 400, "h": 300}
    assert stored_geometry(store, "auto_progress") == {"x": 40, "y": 50, "w": 360, "h": 180}
    remember_geometry(store, "tiny", 10, 10, 20, 20)
    assert stored_geometry(store, "tiny") is None
    reset_geometries(store)
    assert stored_geometry(store, "review") is None
    assert stored_geometry(store, "auto_progress") is None


def test_geometry_is_clamped_to_the_screen():
    box = clamp_geometry({"x": -80, "y": 5000, "w": 800, "h": 600}, 0, 0, 1920, 1080)
    assert box == {"x": 0, "y": 480, "w": 800, "h": 600}


def test_invalid_geometry_is_ignored():
    assert stored_geometry({}, "review") is None
    assert stored_geometry({"review": "nope"}, "review") is None
    assert stored_geometry({"review": {"x": 1, "y": 2}}, "review") is None


def test_unknown_preprocess_strategy_falls_back():
    assert valid_preprocess_strategy("paper_normalize") == "paper_normalize"
    assert valid_preprocess_strategy("nope") == "standard"
    assert valid_preprocess_strategy(None) == "standard"


def test_default_preprocess_strategy_migrates(monkeypatch, tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"engine":{"default_preprocess_strategy":"nope"}}', encoding="utf-8")
    monkeypatch.setattr("listorez2047.config.config_path", lambda: config)
    assert load_config()["engine"]["default_preprocess_strategy"] == "standard"
