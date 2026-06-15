import json
import os
import httpx


class DoclingError(Exception):
    pass


_CONVERT_OPTIONS = json.dumps({
    "to_formats": ["md"],
    "do_ocr": False,
    "pdf_backend": "dlparse_v2",
})


class DoclingClient:
    def __init__(self, base_url: str, timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def convert(self, file_path: str) -> str:
        if not os.path.isfile(file_path):
            raise DoclingError(f"File not found: {file_path!r}")
        try:
            with open(file_path, "rb") as fh:
                file_name = os.path.basename(file_path)
                resp = httpx.post(
                    f"{self.base_url}/v1/convert/file",
                    files={"files": (file_name, fh, "application/octet-stream")},
                    data={"options": _CONVERT_OPTIONS},
                    timeout=self.timeout,
                )
            resp.raise_for_status()
            return resp.json()["document"]["md_content"]
        except DoclingError:
            raise
        except Exception as exc:
            raise DoclingError(f"Docling conversion failed for {file_path!r}: {exc}") from exc
