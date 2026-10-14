from pathlib import Path
from listorez2047.profiles import resolve_output_dir, save_profile, load_profile
from listorez2047.fields import Field
import pytest


def test_resolve_absolute_output_ignores_relative_flag(tmp_path):
    absolute = tmp_path / "out"
    assert resolve_output_dir(str(absolute), relative=True, base=tmp_path) == absolute


def test_resolve_relative_output_against_base(tmp_path):
    base = tmp_path / "pdfs"
    base.mkdir()
    path = resolve_output_dir("results/batch", relative=True, base=base)
    assert path == (base / "results" / "batch").resolve()


def test_profile_roundtrip_stores_output_folder(tmp_path):
    path = tmp_path / "form.pdfocr.json"
    field = Field(1, remember_last_value=True)
    save_profile(
        path,
        fields=[field],
        name_template="{1}",
        page_format="A4",
        custom_mm=(210, 297),
        orientation="portrait",
        ocr_enabled=True,
        auto_deskew=True,
        engine={},
        ui={"ui_language": "ru", "ui_skin": "gas_blue", "ui_icon": "gas", "ui_icon_locked": False},
        output_folder="out/pages",
        output_relative=True,
    )
    loaded = load_profile(path)
    assert loaded["output_folder"] == "out/pages"
    assert loaded["output_relative"] is True
    assert loaded["fields"][0].remember_last_value is True


def test_profile_rejects_invalid_field_geometry(tmp_path):
    path=tmp_path/"bad.pdfocr.json"
    save_profile(path,fields=[Field(1)],name_template="{1}",page_format="A4",
                 custom_mm=(210,297),orientation="portrait",ocr_enabled=True,
                 auto_deskew=True,engine={},ui={})
    data=path.read_text(encoding="utf-8").replace('"x": 0.1','"x": 4.0')
    path.write_text(data,encoding="utf-8")
    with pytest.raises(ValueError):load_profile(path)
