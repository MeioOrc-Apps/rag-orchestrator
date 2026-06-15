from pathlib import Path

from app.pdf_direct import is_digital_pdf

TEXT_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".rst", ".tex", ".csv",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".sql", ".sh", ".bash", ".xml", ".css",
    ".go", ".rs", ".java", ".c", ".cpp", ".h", ".rb", ".php", ".lua",
}

MARKITDOWN_EXTENSIONS = {".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".html", ".htm"}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}


def route(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return "direct"
    if ext == ".pdf":
        return "pdf_direct" if is_digital_pdf(path) else "docling"
    if ext in MARKITDOWN_EXTENSIONS:
        return "markitdown"
    if ext in IMAGE_EXTENSIONS:
        return "docling"
    return "unsupported"
