import pytest
from unittest.mock import patch, MagicMock


class TestDoclingConvert:
    def test_convert_sends_correct_payload(self):
        from app.docling_client import DoclingClient

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"document": {"md_content": "# Hello"}}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            client = DoclingClient("http://docling:5001")
            result = client.convert("/files/doc.pdf")

        call_args = mock_post.call_args
        assert "/v1/convert/source" in call_args.args[0]
        payload = call_args.kwargs["json"]
        assert payload["sources"] == [{"kind": "file", "path": "/files/doc.pdf"}]
        assert payload["options"]["to_formats"] == ["md"]
        assert payload["options"]["do_ocr"] is False
        assert payload["options"]["pdf_backend"] == "dlparse_v2"
        assert result == "# Hello"

    def test_convert_extracts_md_content_from_response(self):
        from app.docling_client import DoclingClient

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"document": {"md_content": "## My Document\n\nContent here."}}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            client = DoclingClient("http://docling:5001")
            result = client.convert("/files/report.docx")

        assert result == "## My Document\n\nContent here."

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
