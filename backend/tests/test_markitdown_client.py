from unittest.mock import MagicMock, patch


def test_convert_to_markdown_calls_convert_and_returns_markdown():
    import app.markitdown_client as mc

    mock_result = MagicMock()
    mock_result.markdown = "# Converted document"

    with patch.object(mc, "_md") as mock_md:
        mock_md.convert.return_value = mock_result
        result = mc.convert_to_markdown("/fake/doc.docx")

    mock_md.convert.assert_called_once_with("/fake/doc.docx")
    assert result == "# Converted document"


def test_convert_to_markdown_uses_module_singleton():
    import app.markitdown_client as mc
    from markitdown import MarkItDown

    assert isinstance(mc._md, MarkItDown)
