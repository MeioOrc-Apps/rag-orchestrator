import pytest


def test_route_md_returns_direct():
    from app.pipeline.router import route
    assert route(".md") == "direct"


def test_route_txt_returns_direct():
    from app.pipeline.router import route
    assert route(".txt") == "direct"


def test_route_markdown_returns_direct():
    from app.pipeline.router import route
    assert route(".markdown") == "direct"


def test_route_case_insensitive():
    from app.pipeline.router import route
    assert route(".MD") == "direct"
    assert route(".TXT") == "direct"


def test_route_pdf_returns_docling():
    from app.pipeline.router import route
    assert route(".pdf") == "docling"


def test_route_docx_returns_docling():
    from app.pipeline.router import route
    assert route(".docx") == "docling"


def test_route_pptx_returns_docling():
    from app.pipeline.router import route
    assert route(".pptx") == "docling"


def test_route_xlsx_returns_docling():
    from app.pipeline.router import route
    assert route(".xlsx") == "docling"


def test_route_html_returns_docling():
    from app.pipeline.router import route
    assert route(".html") == "docling"


def test_route_image_returns_docling():
    from app.pipeline.router import route
    assert route(".png") == "docling"
    assert route(".jpg") == "docling"


def test_route_unknown_raises_value_error():
    from app.pipeline.router import route
    with pytest.raises(ValueError, match="Unknown"):
        route(".xyz")


def test_route_no_extension_raises_value_error():
    from app.pipeline.router import route
    with pytest.raises(ValueError):
        route("")
