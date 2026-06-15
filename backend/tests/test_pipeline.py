import uuid
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


pytestmark = pytest.mark.integration


@pytest.fixture
def pipeline_db(db_session):
    """db_session already has migrations and seeded user via conftest."""
    return db_session


@pytest.fixture
def owner(pipeline_db):
    from app.models import User
    return pipeline_db.query(User).filter(User.username == "sergio").first()


@pytest.fixture
def watched_folder(pipeline_db, owner, tmp_path):
    from app.models import WatchedFolder
    folder = WatchedFolder(
        owner_id=owner.id,
        host_path=str(tmp_path / "source"),
        dest_subdir="docs",
        recursive=True,
        enabled=True,
    )
    pipeline_db.add(folder)
    pipeline_db.commit()
    pipeline_db.refresh(folder)
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    return folder, source_dir


class TestDedup:
    def test_file_with_same_hash_and_status_done_is_skipped(
        self, pipeline_db, owner, watched_folder, tmp_path
    ):
        from app.pipeline.ingestor import run_pipeline
        from app.models import ProcessedFile

        folder, source_dir = watched_folder
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        f = source_dir / "doc.md"
        f.write_text("hello")

        result = run_pipeline(pipeline_db, [folder], owner.id, input_dir)
        assert result["processed"] == 1

        result2 = run_pipeline(pipeline_db, [folder], owner.id, input_dir)
        assert result2["skipped"] == 1
        assert result2["processed"] == 0


class TestDirectRoute:
    def test_md_file_is_copied_to_input_dir(self, pipeline_db, owner, watched_folder, tmp_path):
        from app.pipeline.ingestor import run_pipeline

        folder, source_dir = watched_folder
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        f = source_dir / "note.md"
        f.write_text("# Note")

        run_pipeline(pipeline_db, [folder], owner.id, input_dir)

        dest = input_dir / "docs" / "note.md"
        assert dest.exists()
        assert dest.read_text() == "# Note"

    def test_txt_file_is_copied_to_input_dir(self, pipeline_db, owner, watched_folder, tmp_path):
        from app.pipeline.ingestor import run_pipeline

        folder, source_dir = watched_folder
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        f = source_dir / "readme.txt"
        f.write_text("text content")

        run_pipeline(pipeline_db, [folder], owner.id, input_dir)

        dest = input_dir / "docs" / "readme.txt"
        assert dest.exists()

    def test_nested_file_preserves_structure(self, pipeline_db, owner, watched_folder, tmp_path):
        from app.pipeline.ingestor import run_pipeline

        folder, source_dir = watched_folder
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        sub = source_dir / "sub"
        sub.mkdir()
        f = sub / "deep.md"
        f.write_text("deep content")

        run_pipeline(pipeline_db, [folder], owner.id, input_dir)

        dest = input_dir / "docs" / "sub" / "deep.md"
        assert dest.exists()


class TestRegistration:
    def test_creates_processed_file_with_status_done(
        self, pipeline_db, owner, watched_folder, tmp_path
    ):
        from app.pipeline.ingestor import run_pipeline
        from app.models import ProcessedFile

        folder, source_dir = watched_folder
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        f = source_dir / "doc.md"
        f.write_text("content")

        run_pipeline(pipeline_db, [folder], owner.id, input_dir)

        pf = pipeline_db.query(ProcessedFile).filter(
            ProcessedFile.source_path == str(f),
        ).first()
        assert pf is not None
        assert pf.status == "done"
        assert pf.route == "direct"
        assert pf.processed_at is not None
        assert pf.dest_path is not None

    def test_io_error_creates_failed_record(
        self, pipeline_db, owner, watched_folder, tmp_path
    ):
        from app.pipeline.ingestor import run_pipeline
        from app.models import ProcessedFile

        folder, source_dir = watched_folder
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        f = source_dir / "doc.md"
        f.write_text("content")

        with patch("app.pipeline.ingestor.shutil.copy2", side_effect=OSError("disk full")):
            result = run_pipeline(pipeline_db, [folder], owner.id, input_dir)

        assert result["failed"] == 1
        pf = pipeline_db.query(ProcessedFile).filter(
            ProcessedFile.source_path == str(f)
        ).first()
        assert pf.status == "failed"
        assert "disk full" in pf.error_message

    def test_unknown_extension_creates_failed_record(
        self, pipeline_db, owner, watched_folder, tmp_path
    ):
        from app.pipeline.ingestor import run_pipeline
        from app.models import ProcessedFile

        folder, source_dir = watched_folder
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        f = source_dir / "file.xyz"
        f.write_text("unknown")

        result = run_pipeline(pipeline_db, [folder], owner.id, input_dir)

        assert result["failed"] == 1
        pf = pipeline_db.query(ProcessedFile).first()
        assert pf.status == "failed"


class TestBatchFaultTolerance:
    def test_failure_in_one_file_does_not_stop_others(
        self, pipeline_db, owner, watched_folder, tmp_path
    ):
        from app.pipeline.ingestor import run_pipeline

        folder, source_dir = watched_folder
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        (source_dir / "good.md").write_text("good")
        (source_dir / "bad.xyz").write_text("bad")

        result = run_pipeline(pipeline_db, [folder], owner.id, input_dir)

        assert result["processed"] == 1
        assert result["failed"] == 1
        assert (input_dir / "docs" / "good.md").exists()


class TestSchedulerSkipsFailed:
    def test_scheduler_skips_previously_failed_file(
        self, pipeline_db, owner, watched_folder, tmp_path
    ):
        """Scheduled sync (retry_failed=False) must skip files already marked failed
        so Docling models are not reloaded every 30 minutes for files that won't succeed."""
        from app.pipeline.ingestor import run_pipeline
        from app.models import ProcessedFile

        folder, source_dir = watched_folder
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        f = source_dir / "doc.md"
        f.write_text("content")

        with patch("app.pipeline.ingestor.shutil.copy2", side_effect=OSError("disk full")):
            run_pipeline(pipeline_db, [folder], owner.id, input_dir)

        # Scheduler run: retry_failed=False → skip, return skipped count
        r = run_pipeline(pipeline_db, [folder], owner.id, input_dir, retry_failed=False)
        assert r["processed"] == 0
        assert r["failed"] == 0
        assert r["skipped"] == 1

    def test_manual_sync_retries_failed_file(
        self, pipeline_db, owner, watched_folder, tmp_path
    ):
        """Manual sync (retry_failed=True, the default) still retries failed files."""
        from app.pipeline.ingestor import run_pipeline

        folder, source_dir = watched_folder
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        f = source_dir / "doc.md"
        f.write_text("content")

        with patch("app.pipeline.ingestor.shutil.copy2", side_effect=OSError("disk full")):
            run_pipeline(pipeline_db, [folder], owner.id, input_dir)

        # Manual sync: retry_failed=True (default) → retries and succeeds
        r = run_pipeline(pipeline_db, [folder], owner.id, input_dir, retry_failed=True)
        assert r["processed"] == 1
        assert r["failed"] == 0


class TestRetryFailedFile:
    def test_failed_file_is_retried_on_second_sync(
        self, pipeline_db, owner, watched_folder, tmp_path
    ):
        """A file previously marked 'failed' must be retried, not rejected with a
        unique-constraint violation that breaks the DB session."""
        from app.pipeline.ingestor import run_pipeline
        from app.models import ProcessedFile

        folder, source_dir = watched_folder
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        f = source_dir / "doc.md"
        f.write_text("content")

        # First sync: force a failure via OSError on copy
        with patch("app.pipeline.ingestor.shutil.copy2", side_effect=OSError("disk full")):
            r1 = run_pipeline(pipeline_db, [folder], owner.id, input_dir)
        assert r1["failed"] == 1

        pf = pipeline_db.query(ProcessedFile).filter(
            ProcessedFile.source_path == str(f)
        ).first()
        assert pf.status == "failed"

        # Second sync: fix is in place — should process successfully, no crash
        r2 = run_pipeline(pipeline_db, [folder], owner.id, input_dir)
        assert r2["processed"] == 1
        assert r2["failed"] == 0

        pipeline_db.refresh(pf)
        assert pf.status == "done"
