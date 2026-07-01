"""Tests for Files API — GET /api/files, detail, delete, reindex, retranslate."""
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def file_with_chunks(db_session, tmp_path):
    from app.models import File, Chunk
    from app.pipeline.scanner import compute_hash

    fpath = tmp_path / "doc.md"
    fpath.write_text("Hello world")
    file_row = File(
        path=str(fpath), filename="doc.md", domain="docs",
        file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
        parse_status="done",
    )
    db_session.add(file_row)
    db_session.flush()

    chunks = [
        Chunk(
            file_id=file_row.id, chunk_index=0,
            content_original="Hello world", source_language="en", content_en="Hello world",
            char_count=11, translation_status="done", index_status="done",
            opensearch_id="os-1",
        ),
        Chunk(
            file_id=file_row.id, chunk_index=1,
            content_original="More text here.", source_language="en", content_en="More text here.",
            char_count=15, translation_status="done", index_status="pending",
        ),
    ]
    for c in chunks:
        db_session.add(c)
    db_session.commit()
    db_session.refresh(file_row)
    return file_row


class TestListFiles:
    def test_list_returns_200(self, api_client):
        resp = api_client.get("/api/files")
        assert resp.status_code == 200

    def test_list_returns_paginated_shape(self, api_client):
        resp = api_client.get("/api/files")
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert "limit" in body
        assert "offset" in body

    def test_list_includes_created_files(self, api_client, file_with_chunks):
        resp = api_client.get("/api/files")
        body = resp.json()
        assert body["total"] >= 1
        ids = [item["id"] for item in body["items"]]
        assert str(file_with_chunks.id) in ids

    def test_filter_by_domain(self, api_client, file_with_chunks):
        resp = api_client.get("/api/files?domain=docs")
        body = resp.json()
        for item in body["items"]:
            assert item["domain"] == "docs"

    def test_filter_by_parse_status(self, api_client, file_with_chunks):
        resp = api_client.get("/api/files?parse_status=done")
        body = resp.json()
        for item in body["items"]:
            assert item["parse_status"] == "done"

    def test_soft_deleted_files_excluded(self, api_client, db_session, file_with_chunks):
        from datetime import datetime, timezone
        file_with_chunks.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        resp = api_client.get("/api/files")
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(file_with_chunks.id) not in ids

    def test_pagination_offset(self, api_client, db_session, tmp_path):
        from app.models import File
        from app.pipeline.scanner import compute_hash
        for i in range(3):
            fpath = tmp_path / f"f{i}.md"
            fpath.write_text(f"content {i}")
            db_session.add(File(
                path=str(fpath), filename=f"f{i}.md", domain="docs",
                file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
                parse_status="pending",
            ))
        db_session.commit()

        r1 = api_client.get("/api/files?limit=2&offset=0").json()
        r2 = api_client.get("/api/files?limit=2&offset=2").json()
        ids1 = {i["id"] for i in r1["items"]}
        ids2 = {i["id"] for i in r2["items"]}
        assert ids1.isdisjoint(ids2)


class TestFileDetail:
    def test_get_file_returns_200(self, api_client, file_with_chunks):
        resp = api_client.get(f"/api/files/{file_with_chunks.id}")
        assert resp.status_code == 200

    def test_get_file_returns_chunks_summary(self, api_client, file_with_chunks):
        resp = api_client.get(f"/api/files/{file_with_chunks.id}")
        body = resp.json()
        assert "chunks" in body
        assert body["chunks"]["total"] == 2

    def test_get_nonexistent_file_returns_404(self, api_client):
        import uuid
        resp = api_client.get(f"/api/files/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestDeleteFile:
    def test_delete_sets_deleted_at(self, api_client, db_session, file_with_chunks):
        resp = api_client.delete(f"/api/files/{file_with_chunks.id}")
        assert resp.status_code == 204
        db_session.refresh(file_with_chunks)
        assert file_with_chunks.deleted_at is not None

    def test_delete_marks_chunks_index_status_deleted(self, api_client, db_session, file_with_chunks):
        from app.models import Chunk
        api_client.delete(f"/api/files/{file_with_chunks.id}")
        chunks = db_session.query(Chunk).filter(Chunk.file_id == file_with_chunks.id).all()
        for chunk in chunks:
            assert chunk.index_status == "deleted"

    def test_delete_nonexistent_returns_404(self, api_client):
        import uuid
        resp = api_client.delete(f"/api/files/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestReindexFile:
    def test_reindex_resets_parse_status_to_pending(self, api_client, db_session, file_with_chunks):
        resp = api_client.post(f"/api/files/{file_with_chunks.id}/reindex")
        assert resp.status_code == 200
        db_session.refresh(file_with_chunks)
        assert file_with_chunks.parse_status == "pending"

    def test_reindex_hard_deletes_all_chunks(self, api_client, db_session, file_with_chunks):
        from app.models import Chunk
        file_id = file_with_chunks.id
        api_client.post(f"/api/files/{file_id}/reindex")
        count = db_session.query(Chunk).filter(Chunk.file_id == file_id).count()
        assert count == 0

    def test_reindex_nonexistent_returns_404(self, api_client):
        import uuid
        resp = api_client.post(f"/api/files/{uuid.uuid4()}/reindex")
        assert resp.status_code == 404


class TestRetranslateFile:
    def test_retranslate_resets_failed_chunks_to_pending(self, api_client, db_session, file_with_chunks):
        from app.models import Chunk
        # Mark one chunk as failed
        chunk = db_session.query(Chunk).filter(Chunk.file_id == file_with_chunks.id).first()
        chunk.translation_status = "failed"
        db_session.commit()

        resp = api_client.post(f"/api/files/{file_with_chunks.id}/retranslate")
        assert resp.status_code == 200
        db_session.refresh(chunk)
        assert chunk.translation_status == "pending"

    def test_retranslate_leaves_done_chunks_untouched(self, api_client, db_session, file_with_chunks):
        from app.models import Chunk
        chunks = db_session.query(Chunk).filter(Chunk.file_id == file_with_chunks.id).all()
        for c in chunks:
            c.translation_status = "done"
        db_session.commit()

        api_client.post(f"/api/files/{file_with_chunks.id}/retranslate")
        chunks = db_session.query(Chunk).filter(Chunk.file_id == file_with_chunks.id).all()
        for c in chunks:
            assert c.translation_status == "done"

    def test_retranslate_nonexistent_returns_404(self, api_client):
        import uuid
        resp = api_client.post(f"/api/files/{uuid.uuid4()}/retranslate")
        assert resp.status_code == 404
