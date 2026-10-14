import pymupdf as fitz
import pytest

from listorez2047.pdf_io import PdfDocument


def make_pdf(path, text="hello"):
    doc=fitz.open(); page=doc.new_page(); page.insert_text((72,72),text); doc.save(path); doc.close()


def test_short_native_text_is_detected(tmp_path):
    path=tmp_path/"short.pdf"; make_pdf(path,"OK")
    pdf=PdfDocument(path)
    try:
        assert pdf.textful == [True]
        assert pdf.kind == "digital"
    finally:pdf.close()


def test_save_page_is_one_page_and_never_overwrites(tmp_path):
    source=tmp_path/"source.pdf"; make_pdf(source)
    pdf=PdfDocument(source); target=tmp_path/"page.pdf"
    try:
        pdf.save_page(0,target)
        with fitz.open(target) as saved:
            assert len(saved)==1
            assert "hello" in saved[0].get_text()
        with pytest.raises(FileExistsError):pdf.save_page(0,target)
    finally:pdf.close()


def test_render_clips_to_field_rectangle(tmp_path):
    source=tmp_path/"source.pdf"; make_pdf(source)
    pdf=PdfDocument(source)
    try:
        pix=pdf.render(0,300,rect=type("Rect",(),{"x":0.1,"y":0.1,"w":0.2,"h":0.1})(),max_side=3508)
        assert pix.width < 600 and pix.height < 400
    finally:pdf.close()
