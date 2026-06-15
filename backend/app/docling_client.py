import base64
import os

import httpx


class DoclingError(Exception):
    pass


class DoclingClient:
    def __init__(self, base_url: str, timeout: float = 600.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def convert(self, file_path: str) -> str:
        if not os.path.isfile(file_path):
            raise DoclingError(f"File not found: {file_path!r}")
        try:
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            payload = {
                "sources": [
                    {
                        "kind": "file",
                        "base64_string": b64,
                        "filename": os.path.basename(file_path),
                    }
                ],
                "options": {
                    "to_formats": ["md"],
                    "do_ocr": False,
                    # pypdfium2: fast text extraction, no ML layout models
                    "pdf_backend": "pypdfium2",
                },
            }
            resp = httpx.post(
                f"{self.base_url}/v1/convert/source",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()["document"]["md_content"]
        except DoclingError:
            raise
        except Exception as exc:
            raise DoclingError(f"Docling conversion failed for {file_path!r}: {exc}") from exc
