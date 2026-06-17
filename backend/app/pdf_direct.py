import pymupdf
import pymupdf4llm


def is_digital_pdf(path: str, min_text_page_ratio: float = 0.5) -> bool:
    try:
        doc = pymupdf.open(path)
        try:
            num_pages = doc.page_count
            if num_pages == 0:
                return False
            pages_with_text = sum(
                1 for page in doc if len(page.get_text().strip()) > 10
            )
            return (pages_with_text / num_pages) >= min_text_page_ratio
        finally:
            doc.close()
    except Exception:
        return False


def convert_to_markdown(path: str) -> str:
    return pymupdf4llm.to_markdown(path)
