from unittest.mock import patch

import pytest


# --- TEXT / CODE (direct route) ---

def test_route_md_returns_direct():
    from app.pipeline.router import route
    assert route("note.md") == "direct"


def test_route_txt_returns_direct():
    from app.pipeline.router import route
    assert route("readme.txt") == "direct"


def test_route_markdown_returns_direct():
    from app.pipeline.router import route
    assert route("file.markdown") == "direct"


def test_route_rst_returns_direct():
    from app.pipeline.router import route
    assert route("doc.rst") == "direct"


def test_route_py_returns_direct():
    from app.pipeline.router import route
    assert route("script.py") == "direct"


def test_route_js_returns_direct():
    from app.pipeline.router import route
    assert route("app.js") == "direct"


def test_route_ts_returns_direct():
    from app.pipeline.router import route
    assert route("main.ts") == "direct"


def test_route_json_returns_direct():
    from app.pipeline.router import route
    assert route("config.json") == "direct"


def test_route_yaml_returns_direct():
    from app.pipeline.router import route
    assert route("config.yaml") == "direct"


def test_route_go_returns_direct():
    from app.pipeline.router import route
    assert route("main.go") == "direct"


def test_route_sql_returns_direct():
    from app.pipeline.router import route
    assert route("schema.sql") == "direct"


def test_route_csv_returns_direct():
    from app.pipeline.router import route
    assert route("data.csv") == "direct"


def test_route_sh_returns_direct():
    from app.pipeline.router import route
    assert route("deploy.sh") == "direct"


def test_route_case_insensitive_direct():
    from app.pipeline.router import route
    assert route("README.MD") == "direct"
    assert route("SCRIPT.PY") == "direct"
    assert route("DATA.JSON") == "direct"


# --- PDF (content-based) ---

def test_route_pdf_digital_returns_pdf_direct():
    from app.pipeline.router import route
    with patch("app.pipeline.router.is_digital_pdf", return_value=True):
        assert route("report.pdf") == "pdf_direct"


def test_route_pdf_scanned_returns_docling():
    from app.pipeline.router import route
    with patch("app.pipeline.router.is_digital_pdf", return_value=False):
        assert route("scan.pdf") == "docling"


def test_route_pdf_case_insensitive():
    from app.pipeline.router import route
    with patch("app.pipeline.router.is_digital_pdf", return_value=True):
        assert route("REPORT.PDF") == "pdf_direct"


# --- OFFICE / HTML (markitdown route) ---

def test_route_docx_returns_markitdown():
    from app.pipeline.router import route
    assert route("slides.docx") == "markitdown"


def test_route_doc_returns_markitdown():
    from app.pipeline.router import route
    assert route("old.doc") == "markitdown"


def test_route_pptx_returns_markitdown():
    from app.pipeline.router import route
    assert route("deck.pptx") == "markitdown"


def test_route_ppt_returns_markitdown():
    from app.pipeline.router import route
    assert route("old.ppt") == "markitdown"


def test_route_xlsx_returns_markitdown():
    from app.pipeline.router import route
    assert route("sheet.xlsx") == "markitdown"


def test_route_html_returns_markitdown():
    from app.pipeline.router import route
    assert route("page.html") == "markitdown"


def test_route_htm_returns_markitdown():
    from app.pipeline.router import route
    assert route("page.htm") == "markitdown"


# --- IMAGES (docling route) ---

def test_route_png_returns_docling():
    from app.pipeline.router import route
    assert route("photo.png") == "docling"


def test_route_jpg_returns_docling():
    from app.pipeline.router import route
    assert route("scan.jpg") == "docling"


def test_route_jpeg_returns_docling():
    from app.pipeline.router import route
    assert route("scan.jpeg") == "docling"


def test_route_tiff_returns_docling():
    from app.pipeline.router import route
    assert route("scan.tiff") == "docling"


def test_route_bmp_returns_docling():
    from app.pipeline.router import route
    assert route("image.bmp") == "docling"


def test_route_webp_returns_docling():
    from app.pipeline.router import route
    assert route("photo.webp") == "docling"


# --- UNSUPPORTED ---

def test_route_unknown_returns_unsupported():
    from app.pipeline.router import route
    assert route("file.xyz") == "unsupported"


def test_route_no_extension_returns_unsupported():
    from app.pipeline.router import route
    assert route("Makefile") == "unsupported"


def test_route_case_insensitive_for_images():
    from app.pipeline.router import route
    assert route("PHOTO.PNG") == "docling"
    assert route("IMAGE.JPG") == "docling"
