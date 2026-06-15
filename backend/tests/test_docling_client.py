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
    def test_convert_sends_file_as_multipart(self):
        from app.docling_client import DoclingClient

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test content")
            tmp_path = f.name

        try:
            with patch("httpx.post", return_value=_make_mock_resp()) as mock_post:
                client = DoclingClient("http://docling:5001")
                result = client.convert(tmp_path)

            call_args = mock_post.call_args
            assert "/v1/convert/file" in call_args.args[0]
            assert "files" in call_args.kwargs
            assert call_args.kwargs.get("json") is None
            # options sent as form data to request do_ocr=false
            data = call_args.kwargs.get("data", {})
            assert "options" in data
            import json
            opts = json.loads(data["options"])
            assert opts["do_ocr"] is False
            assert result == "# Hello"
        finally:
            os.unlink(tmp_path)

    def test_convert_uses_300s_timeout(self):
        from app.docling_client import DoclingClient

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test content")
            tmp_path = f.name

        try:
            with patch("httpx.post", return_value=_make_mock_resp()) as mock_post:
                client = DoclingClient("http://docling:5001")
                client.convert(tmp_path)

            timeout = mock_post.call_args.kwargs.get("timeout")
            assert timeout >= 300
        finally:
            os.unlink(tmp_path)

    def test_convert_extracts_md_content_from_response(self):
        from app.docling_client import DoclingClient

        content = "## My Document\n\nContent here."
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"PK fake docx bytes")
            tmp_path = f.name

        try:
            with patch("httpx.post", return_value=_make_mock_resp(content)):
                client = DoclingClient("http://docling:5001")
                result = client.convert(tmp_path)

            assert result == content
        finally:
            os.unlink(tmp_path)

    def test_convert_raises_docling_error_if_file_not_found(self):
        from app.docling_client import DoclingClient, DoclingError

        client = DoclingClient("http://docling:5001")
        with pytest.raises(DoclingError, match="not found"):
            client.convert("/nonexistent/path/doc.pdf")

    def test_convert_raises_docling_error_on_http_failure(self):
        from app.docling_client import DoclingClient, DoclingError

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF content")
            tmp_path = f.name

        try:
            with patch("httpx.post", return_value=mock_resp):
                client = DoclingClient("http://docling:5001")
                with pytest.raises(DoclingError):
                    client.convert(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_convert_raises_docling_error_on_network_failure(self):
        from app.docling_client import DoclingClient, DoclingError

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF content")
            tmp_path = f.name

        try:
            with patch("httpx.post", side_effect=Exception("connection refused")):
                client = DoclingClient("http://docling:5001")
                with pytest.raises(DoclingError):
                    client.convert(tmp_path)
        finally:
            os.unlink(tmp_path)
