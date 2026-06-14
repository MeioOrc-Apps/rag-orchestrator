_DIRECT = {".md", ".txt", ".markdown"}
_DOCLING = {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}


def route(extension: str) -> str:
    ext = extension.lower()
    if ext in _DIRECT:
        return "direct"
    if ext in _DOCLING:
        return "docling"
    raise ValueError(f"Unknown file type extension: {extension!r}")
