import httpx


class DoclingError(Exception):
    pass


class DoclingClient:
    def __init__(self, base_url: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def convert(self, file_path: str) -> str:
        payload = {
            "sources": [{"kind": "file", "path": file_path}],
            "options": {
                "to_formats": ["md"],
                "do_ocr": False,
                "pdf_backend": "dlparse_v2",
            },
        }
        try:
            resp = httpx.post(
                f"{self.base_url}/v1/convert/source",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()["document"]["md_content"]
        except Exception as exc:
            raise DoclingError(f"Docling conversion failed for {file_path!r}: {exc}") from exc
