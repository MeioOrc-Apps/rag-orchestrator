"""Integration tests for delete_job — real DB, mocked OpenSearchClient."""
import pytest
from unittest.mock import patch

pytestmark = pytest.mark.integration


@pytest.fixture
def chunk_marked_deleted(db_session, tmp_path):
    """Chunk with index_status='deleted' and an opensearch_id."""
    from app.models import File, Chunk
    from app.pipeline.scanner import compute_hash

    fpath = tmp_path / "old.md"
    fpath.write_text("old content")
    file_row = File(
        path=str(fpath), filename="old.md", domain="docs",
        file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
        parse_status="done",
    )
    db_session.add(file_row)
    db_session.flush()

    chunk = Chunk(
        file_id=file_row.id, chunk_index=0,
        content_original="old content", source_language="en", content_en="old content",
        char_count=11, translation_status="done",
        index_status="deleted", opensearch_id="os-old-1",
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)
    return chunk, file_row


class TestDeleteJobWithOpenSearchId:
    def test_deleted_chunk_with_os_id_is_hard_deleted_from_db(
        self, db_session, chunk_marked_deleted
    ):
        from app.jobs.delete_job import run_delete
        from app.models import Chunk

        chunk, _ = chunk_marked_deleted
        chunk_id = chunk.id

        with patch("app.jobs.delete_job.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.bulk_delete.return_value = ["os-old-1"]
            run_delete(db_session)

        assert db_session.query(Chunk).filter(Chunk.id == chunk_id).first() is None

    def test_bulk_delete_called_with_correct_os_id(self, db_session, chunk_marked_deleted):
        from app.jobs.delete_job import run_delete

        chunk, _ = chunk_marked_deleted
        with patch("app.jobs.delete_job.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.bulk_delete.return_value = ["os-old-1"]
            run_delete(db_session)

        instance.bulk_delete.assert_called_once_with("docs", ["os-old-1"])

    def test_bulk_delete_grouped_by_domain(self, db_session, tmp_path):
        from app.jobs.delete_job import run_delete
        from app.models import File, Chunk
        from app.pipeline.scanner import compute_hash

        for domain in ("alpha", "beta"):
            fpath = tmp_path / f"{domain}.md"
            fpath.write_text("content")
            file_row = File(
                path=str(fpath), filename=f"{domain}.md", domain=domain,
                file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
                parse_status="done",
            )
            db_session.add(file_row)
            db_session.flush()
            chunk = Chunk(
                file_id=file_row.id, chunk_index=0,
                content_original="x", source_language="en", content_en="x",
                char_count=1, translation_status="done",
                index_status="deleted", opensearch_id=f"os-{domain}",
            )
            db_session.add(chunk)
        db_session.commit()

        with patch("app.jobs.delete_job.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.bulk_delete.return_value = ["os-alpha"]
            run_delete(db_session)

        # Called once per domain
        assert instance.bulk_delete.call_count == 2
        domains_called = {call[0][0] for call in instance.bulk_delete.call_args_list}
        assert domains_called == {"alpha", "beta"}

    def test_os_delete_failure_leaves_chunk_in_db(self, db_session, chunk_marked_deleted):
        """If OpenSearch does not confirm deletion, chunk stays in DB."""
        from app.jobs.delete_job import run_delete
        from app.models import Chunk

        chunk, _ = chunk_marked_deleted
        chunk_id = chunk.id

        with patch("app.jobs.delete_job.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.bulk_delete.return_value = []  # nothing confirmed
            run_delete(db_session)

        assert db_session.query(Chunk).filter(Chunk.id == chunk_id).first() is not None


class TestDeleteJobWithoutOpenSearchId:
    def test_deleted_chunk_without_os_id_hard_deleted_directly(self, db_session, tmp_path):
        """Chunk marked deleted but never indexed → remove from DB, skip OS call."""
        from app.jobs.delete_job import run_delete
        from app.models import File, Chunk
        from app.pipeline.scanner import compute_hash

        fpath = tmp_path / "never_indexed.md"
        fpath.write_text("text")
        file_row = File(
            path=str(fpath), filename="never_indexed.md", domain="docs",
            file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
            parse_status="done",
        )
        db_session.add(file_row)
        db_session.flush()
        chunk = Chunk(
            file_id=file_row.id, chunk_index=0,
            content_original="text", source_language="en",
            char_count=4, translation_status="pending",
            index_status="deleted", opensearch_id=None,
        )
        db_session.add(chunk)
        db_session.commit()
        chunk_id = chunk.id

        with patch("app.jobs.delete_job.OpenSearchClient") as MockOS:
            run_delete(db_session)
            MockOS.return_value.bulk_delete.assert_not_called()

        assert db_session.query(Chunk).filter(Chunk.id == chunk_id).first() is None

    def test_run_delete_returns_counts(self, db_session, chunk_marked_deleted):
        from app.jobs.delete_job import run_delete

        chunk, _ = chunk_marked_deleted
        with patch("app.jobs.delete_job.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.bulk_delete.return_value = ["os-old-1"]
            result = run_delete(db_session)

        assert "deleted_from_os" in result
        assert "deleted_from_db" in result
        assert result["deleted_from_db"] >= 1
