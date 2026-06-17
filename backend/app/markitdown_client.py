from markitdown import MarkItDown

_md = MarkItDown()


def convert_to_markdown(path: str) -> str:
    result = _md.convert(path)
    return result.markdown
