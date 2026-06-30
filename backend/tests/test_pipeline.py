"""
Pipeline tests — scan-based behavior (etapa 12+).
Legacy copy-to-input-dir behavior removed; scan_job is tested in test_scan_job.py.
These tests cover the scanner and router primitives still used by scan_job.
"""
import pytest
from pathlib import Path

pytestmark = pytest.mark.integration


class TestScanner:
    def test_compute_hash_is_stable(self, tmp_path):
        from app.pipeline.scanner import compute_hash
        f = tmp_path / "file.txt"
        f.write_bytes(b"hello")
        assert compute_hash(f) == compute_hash(f)

    def test_compute_hash_changes_when_content_changes(self, tmp_path):
        from app.pipeline.scanner import compute_hash
        f = tmp_path / "file.txt"
        f.write_bytes(b"hello")
        h1 = compute_hash(f)
        f.write_bytes(b"world")
        h2 = compute_hash(f)
        assert h1 != h2

    def test_scan_returns_files_in_dir(self, tmp_path):
        from app.pipeline.scanner import scan
        (tmp_path / "a.md").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        result = scan(tmp_path, recursive=False)
        names = {p.name for p in result}
        assert names == {"a.md", "b.txt"}

    def test_scan_recursive_finds_nested_files(self, tmp_path):
        from app.pipeline.scanner import scan
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.md").write_text("c")
        result = scan(tmp_path, recursive=True)
        assert any(p.name == "c.md" for p in result)

    def test_scan_nonrecursive_ignores_subdirs(self, tmp_path):
        from app.pipeline.scanner import scan
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.md").write_text("c")
        (tmp_path / "top.md").write_text("top")
        result = scan(tmp_path, recursive=False)
        names = {p.name for p in result}
        assert "c.md" not in names
        assert "top.md" in names

    def test_scan_missing_dir_returns_empty(self, tmp_path):
        from app.pipeline.scanner import scan
        result = scan(tmp_path / "nonexistent", recursive=True)
        assert result == []


class TestRouter:
    def test_md_routes_direct(self, tmp_path):
        from app.pipeline.router import route
        f = tmp_path / "doc.md"
        f.write_text("content")
        assert route(str(f)) == "direct"

    def test_txt_routes_direct(self, tmp_path):
        from app.pipeline.router import route
        f = tmp_path / "doc.txt"
        f.write_text("content")
        assert route(str(f)) == "direct"

    def test_unknown_extension_routes_unsupported(self, tmp_path):
        from app.pipeline.router import route
        f = tmp_path / "doc.xyz"
        f.write_text("content")
        assert route(str(f)) == "unsupported"
