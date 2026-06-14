import hashlib
from pathlib import Path


def compute_hash(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def scan(folder_path: Path, recursive: bool = True) -> list[Path]:
    if not folder_path.is_dir():
        return []
    if recursive:
        return [p for p in folder_path.rglob("*") if p.is_file()]
    return [p for p in folder_path.iterdir() if p.is_file()]
