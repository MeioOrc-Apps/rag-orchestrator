import pymupdf
import pytest


def _make_text_pdf(path, texts=("Enough text on this page to count as digital content",)):
    doc = pymupdf.open()
    for text in texts:
        page = doc.new_page()
        page.insert_text((50, 72), text, fontsize=12)
    doc.save(str(path))
    doc.close()


def _make_image_only_pdf(path, n_pages=1):
    doc = pymupdf.open()
    for _ in range(n_pages):
        page = doc.new_page()
        page.draw_rect(pymupdf.Rect(10, 10, 200, 200), color=(0, 0, 0))
    doc.save(str(path))
    doc.close()


class TestIsDigitalPdf:
    def test_returns_true_for_pdf_with_text(self, tmp_path):
        from app.pdf_direct import is_digital_pdf

        p = tmp_path / "digital.pdf"
        _make_text_pdf(p)
        assert is_digital_pdf(str(p)) is True

    def test_returns_false_for_image_only_pdf(self, tmp_path):
        from app.pdf_direct import is_digital_pdf

        p = tmp_path / "scanned.pdf"
        _make_image_only_pdf(p)
        assert is_digital_pdf(str(p)) is False

    def test_returns_false_for_zero_page_pdf(self):
        from app.pdf_direct import is_digital_pdf
        from unittest.mock import MagicMock, patch

        # pymupdf refuses to save 0-page PDFs to disk; test via mock
        mock_doc = MagicMock()
        mock_doc.page_count = 0

        with patch("pymupdf.open", return_value=mock_doc):
            assert is_digital_pdf("/fake/empty.pdf") is False

        mock_doc.close.assert_called_once()

    def test_returns_false_for_corrupt_file(self, tmp_path):
        from app.pdf_direct import is_digital_pdf

        p = tmp_path / "corrupt.pdf"
        p.write_bytes(b"this is not a pdf at all")
        assert is_digital_pdf(str(p)) is False

    def test_respects_ratio_parameter(self, tmp_path):
        from app.pdf_direct import is_digital_pdf

        p = tmp_path / "mixed.pdf"
        # 2 text pages + 1 image-only page = ratio 2/3 ≈ 0.667
        doc = pymupdf.open()
        for _ in range(2):
            page = doc.new_page()
            page.insert_text((50, 72), "Enough text on this page to count as digital content")
        page = doc.new_page()
        page.draw_rect(pymupdf.Rect(10, 10, 200, 200), color=(0, 0, 0))
        doc.save(str(p))
        doc.close()

        assert is_digital_pdf(str(p)) is True  # 0.667 >= 0.5
        assert is_digital_pdf(str(p), min_text_page_ratio=0.8) is False  # 0.667 < 0.8


class TestConvertToMarkdown:
    def test_returns_string_with_text(self, tmp_path):
        from app.pdf_direct import convert_to_markdown

        p = tmp_path / "digital.pdf"
        _make_text_pdf(p, texts=("Hello from digital PDF",))
        result = convert_to_markdown(str(p))

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Hello" in result
