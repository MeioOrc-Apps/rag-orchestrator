import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock


def _make_mock_resp(md_content: str = "# Hello") -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"document": {"md_content": md_content}}
    mock.raise_for_status = MagicMock()
    return mock


class TestDoclingConvert:
    def test_convert_sends_source_request_with_options(self):
        from app.docling_client import DoclingClient

        with patch("httpx.post", return_value=_make_mock_resp()) as mock_post:
            client = DoclingClient("http://docling:5001")
            result = client.convert("/files/doc.pdf")

        call_args = mock_post.call_args
        assert "/v1/convert/source" in call_args.args[0]
        payload = call_args.kwargs["json"]
        assert payload["sources"] == [{"kind": "file", "path": "/files/doc.pdf"}]
        assert payload["options"]["do_ocr"] is False
        assert payload["options"]["pdf_backend"] == "dlparse_v2"
        assert payload["options"]["to_formats"] == ["md"]
        assert result == "# Hello"

    def test_convert_uses_300s_timeout(self):
        from app.docling_client import DoclingClient

        with patch("httpx.post", return_value=_make_mock_resp()) as mock_post:
            client = DoclingClient("http://docling:5001")
            client.convert("/files/doc.pdf")

        timeout = mock_post.call_args.kwargs.get("timeout")
        assert timeout >= 300

    def test_convert_extracts_md_content_from_response(self):
        from app.docling_client import DoclingClient

        content = "## My Document\n\nContent here."
        with patch("httpx.post", return_value=_make_mock_resp(content)):
            client = DoclingClient("http://docling:5001")
            result = client.convert("/files/report.docx")

        assert result == content

    def test_convert_raises_docling_error_on_http_failure(self):
        from app.docling_client import DoclingClient, DoclingError

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")

        with patch("httpx.post", return_value=mock_resp):
            client = DoclingClient("http://docling:5001")
            with pytest.raises(DoclingError):
                client.convert("/files/doc.pdf")

    def test_convert_raises_docling_error_on_network_failure(self):
        from app.docling_client import DoclingClient, DoclingError

        with patch("httpx.post", side_effect=Exception("connection refused")):
            client = DoclingClient("http://docling:5001")
            with pytest.raises(DoclingError):
                client.convert("/files/doc.pdf")
