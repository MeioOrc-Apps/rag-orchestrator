"""Tests for Admin API — GET /admin/stats, failed, retry, reindex-all, forcemerge."""
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.integration


@pytest.fixture
def seeded_files(db_session, tmp_path):
    """Insert files and chunks in various states for admin stat tests."""
    from app.models import File, Chunk
    from app.pipeline.scanner import compute_hash

    files = {}
    for name, parse_status in [("done.md", "done"), ("pending.md", "pending"), ("failed.md", "failed")]:
        fpath = tmp_path / name
        fpath.write_text(f"content of {name}")
        f = File(
            path=str(fpath), filename=name, domain="docs",
            file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
            parse_status=parse_status,
        )
        db_session.add(f)
        files[parse_status] = f
    db_session.flush()

    # chunks for the done file
    done_file = files["done"]
    for i, (ts, ix) in enumerate([("done", "done"), ("failed", "failed"), ("pending", "pending")]):
        db_session.add(Chunk(
            file_id=done_file.id, chunk_index=i,
            content_original=f"chunk {i}", source_language="en",
            char_count=7, translation_status=ts, index_status=ix,
        ))
    db_session.commit()
    return files


class TestAdminStats:
    def test_stats_returns_200(self, api_client):
        resp = api_client.get("/api/admin/stats")
        assert resp.status_code == 200

    def test_stats_has_files_section(self, api_client, seeded_files):
        resp = api_client.get("/api/admin/stats")
        body = resp.json()
        assert "files" in body
        assert "total" in body["files"]
        assert "by_parse_status" in body["files"]

    def test_stats_has_chunks_section(self, api_client, seeded_files):
        resp = api_client.get("/api/admin/stats")
        body = resp.json()
        assert "chunks" in body
        assert "total" in body["chunks"]

    def test_stats_counts_files_correctly(self, api_client, seeded_files):
        resp = api_client.get("/api/admin/stats")
        body = resp.json()
        assert body["files"]["total"] == 3
        by_status = body["files"]["by_parse_status"]
        assert by_status.get("done", 0) == 1
        assert by_status.get("pending", 0) == 1
        assert by_status.get("failed", 0) == 1

    def test_stats_counts_chunks_by_index_status(self, api_client, seeded_files):
        resp = api_client.get("/api/admin/stats")
        body = resp.json()
        by_idx = body["chunks"].get("by_index_status", {})
        assert by_idx.get("done", 0) == 1
        assert by_idx.get("failed", 0) == 1
        assert by_idx.get("pending", 0) == 1


class TestAdminFailed:
    def test_failed_returns_200(self, api_client):
        resp = api_client.get("/api/admin/failed")
        assert resp.status_code == 200

    def test_failed_lists_failed_files(self, api_client, seeded_files):
        resp = api_client.get("/api/admin/failed")
        body = resp.json()
        assert "failed_files" in body
        ids = [f["id"] for f in body["failed_files"]]
        assert str(seeded_files["failed"].id) in ids

    def test_failed_does_not_include_done_files(self, api_client, seeded_files):
        resp = api_client.get("/api/admin/failed")
        body = resp.json()
        ids = [f["id"] for f in body["failed_files"]]
        assert str(seeded_files["done"].id) not in ids

    def test_failed_lists_failed_chunks(self, api_client, seeded_files):
        resp = api_client.get("/api/admin/failed")
        body = resp.json()
        assert "failed_chunks" in body
        assert len(body["failed_chunks"]) >= 1


class TestAdminRetryFailed:
    def test_retry_failed_returns_200(self, api_client):
        resp = api_client.post("/api/admin/retry-failed")
        assert resp.status_code == 200

    def test_retry_failed_resets_failed_files_to_pending(self, api_client, db_session, seeded_files):
        api_client.post("/api/admin/retry-failed")
        db_session.refresh(seeded_files["failed"])
        assert seeded_files["failed"].parse_status == "pending"

    def test_retry_failed_resets_failed_chunks_translation(self, api_client, db_session, seeded_files):
        from app.models import Chunk
        api_client.post("/api/admin/retry-failed")
        failed_chunks = (
            db_session.query(Chunk)
            .filter(Chunk.file_id == seeded_files["done"].id, Chunk.translation_status == "failed")
            .all()
        )
        assert len(failed_chunks) == 0

    def test_retry_failed_resets_failed_chunks_index(self, api_client, db_session, seeded_files):
        from app.models import Chunk
        api_client.post("/api/admin/retry-failed")
        failed_chunks = (
            db_session.query(Chunk)
            .filter(Chunk.file_id == seeded_files["done"].id, Chunk.index_status == "failed")
            .all()
        )
        assert len(failed_chunks) == 0

    def test_retry_leaves_done_files_untouched(self, api_client, db_session, seeded_files):
        api_client.post("/api/admin/retry-failed")
        db_session.refresh(seeded_files["done"])
        assert seeded_files["done"].parse_status == "done"


class TestAdminReindexAll:
    def _mock_os(self):
        mock = MagicMock()
        mock.delete_all_docs.return_value = 0
        return mock

    def test_reindex_all_returns_200(self, api_client):
        with patch("app.routers.admin.OpenSearchClient", return_value=self._mock_os()):
            resp = api_client.post("/api/admin/reindex-all")
        assert resp.status_code == 200

    def test_reindex_all_resets_all_files_to_pending(self, api_client, db_session, seeded_files):
        with patch("app.routers.admin.OpenSearchClient", return_value=self._mock_os()):
            api_client.post("/api/admin/reindex-all")
        from app.models import File
        for f in db_session.query(File).filter(File.deleted_at.is_(None)).all():
            assert f.parse_status == "pending"

    def test_reindex_all_hard_deletes_all_chunks(self, api_client, db_session, seeded_files):
        from app.models import Chunk
        with patch("app.routers.admin.OpenSearchClient", return_value=self._mock_os()):
            api_client.post("/api/admin/reindex-all")
        assert db_session.query(Chunk).count() == 0

    def test_reindex_all_clears_opensearch_per_domain(self, api_client, db_session, seeded_files):
        mock_os = self._mock_os()
        with patch("app.routers.admin.OpenSearchClient", return_value=mock_os):
            api_client.post("/api/admin/reindex-all")
        mock_os.delete_all_docs.assert_called_with("docs")


class TestAdminForceMerge:
    def test_forcemerge_returns_200(self, api_client):
        with patch("app.routers.admin.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.forcemerge.return_value = None
            resp = api_client.post("/api/admin/forcemerge")
        assert resp.status_code == 200

    def test_forcemerge_calls_opensearch_forcemerge_per_domain(self, api_client, db_session, seeded_files):
        with patch("app.routers.admin.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.forcemerge.return_value = None
            api_client.post("/api/admin/forcemerge")
        # "docs" domain is the only one in seeded_files
        instance.forcemerge.assert_called_with("docs")
