from pathlib import Path
import pytest


class TestComputeHash:
    def test_same_content_same_hash(self, tmp_path):
        from app.pipeline.scanner import compute_hash
        f = tmp_path / "a.md"
        f.write_text("hello world")
        assert compute_hash(f) == compute_hash(f)

    def test_different_content_different_hash(self, tmp_path):
        from app.pipeline.scanner import compute_hash
        f1 = tmp_path / "a.md"
        f2 = tmp_path / "b.md"
        f1.write_text("hello")
        f2.write_text("world")
        assert compute_hash(f1) != compute_hash(f2)

    def test_same_content_different_files_same_hash(self, tmp_path):
        from app.pipeline.scanner import compute_hash
        f1 = tmp_path / "a.md"
        f2 = tmp_path / "b.md"
        f1.write_text("same content")
        f2.write_text("same content")
        assert compute_hash(f1) == compute_hash(f2)

    def test_hash_is_stable_hex_string(self, tmp_path):
        from app.pipeline.scanner import compute_hash
        f = tmp_path / "x.txt"
        f.write_text("content")
        h = compute_hash(f)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest


class TestScan:
    def test_scan_lists_files_in_flat_directory(self, tmp_path):
        from app.pipeline.scanner import scan
        (tmp_path / "a.md").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        result = scan(tmp_path, recursive=True)
        assert len(result) == 2

    def test_scan_recursive_finds_nested_files(self, tmp_path):
        from app.pipeline.scanner import scan
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "top.md").write_text("top")
        (sub / "nested.md").write_text("nested")
        result = scan(tmp_path, recursive=True)
        assert len(result) == 2

    def test_scan_non_recursive_skips_subdirectories(self, tmp_path):
        from app.pipeline.scanner import scan
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "top.md").write_text("top")
        (sub / "nested.md").write_text("nested")
        result = scan(tmp_path, recursive=False)
        assert len(result) == 1
        assert result[0].name == "top.md"

    def test_scan_empty_directory_returns_empty(self, tmp_path):
        from app.pipeline.scanner import scan
        result = scan(tmp_path, recursive=True)
        assert result == []

    def test_scan_returns_paths(self, tmp_path):
        from app.pipeline.scanner import scan
        (tmp_path / "x.md").write_text("x")
        result = scan(tmp_path)
        assert all(isinstance(p, Path) for p in result)
