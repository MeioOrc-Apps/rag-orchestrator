import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def mock_is_digital_pdf():
    """All PDFs in docling tests are scanned (no text layer)."""
    with patch("app.pipeline.router.is_digital_pdf", return_value=False):
        yield


@pytest.fixture
def pipeline_env(db_session, tmp_path):
    from app.models import User, WatchedFolder
    owner = db_session.query(User).filter(User.username == "sergio").first()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    folder = WatchedFolder(
        owner_id=owner.id,
        host_path=str(source_dir),
        dest_subdir="docs",
        recursive=True,
        enabled=True,
    )
    db_session.add(folder)
    db_session.commit()
    db_session.refresh(folder)

    return db_session, owner, [folder], source_dir, input_dir


def _make_docling_client(md_content="# Converted"):
    from app.docling_client import DoclingClient
    mock = MagicMock(spec=DoclingClient)
    mock.convert.return_value = md_content
    return mock


class TestDoclingRoute:
    def test_pdf_converted_and_saved_as_md(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline
        db, owner, folders, source, input_dir = pipeline_env

        pdf = source / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        docling = _make_docling_client("# Report\n\nContent.")
        result = run_pipeline(db, folders, owner.id, input_dir, docling_client=docling)

        assert result["processed"] == 1
        dest = input_dir / "docs" / "report.md"
        assert dest.exists()
        assert dest.read_text() == "# Report\n\nContent."

    def test_docling_error_marks_file_failed_batch_continues(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline
        from app.docling_client import DoclingError
        db, owner, folders, source, input_dir = pipeline_env

        (source / "bad.pdf").write_bytes(b"%PDF bad")
        (source / "good.md").write_text("good")

        docling = MagicMock()
        docling.convert.side_effect = DoclingError("Docling down")

        result = run_pipeline(db, folders, owner.id, input_dir, docling_client=docling)

        assert result["failed"] == 1
        assert result["processed"] == 1

    def test_docling_failed_file_has_error_message(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline
        from app.docling_client import DoclingError
        from app.models import ProcessedFile
        db, owner, folders, source, input_dir = pipeline_env

        pdf = source / "corrupt.pdf"
        pdf.write_bytes(b"bad")

        docling = MagicMock()
        docling.convert.side_effect = DoclingError("conversion failed")

        run_pipeline(db, folders, owner.id, input_dir, docling_client=docling)

        pf = db.query(ProcessedFile).filter(ProcessedFile.source_path == str(pdf)).first()
        assert pf.status == "failed"
        assert "conversion failed" in pf.error_message

    def test_dedup_applies_to_docling_route(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline
        db, owner, folders, source, input_dir = pipeline_env

        pdf = source / "dup.pdf"
        pdf.write_bytes(b"%PDF content")

        docling = _make_docling_client("# Dup")
        run_pipeline(db, folders, owner.id, input_dir, docling_client=docling)
        result2 = run_pipeline(db, folders, owner.id, input_dir, docling_client=docling)

        assert result2["skipped"] == 1
        assert docling.convert.call_count == 1

    def test_unknown_extension_fails_without_calling_docling(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline
        db, owner, folders, source, input_dir = pipeline_env

        (source / "file.xyz").write_text("??")

        docling = _make_docling_client()
        result = run_pipeline(db, folders, owner.id, input_dir, docling_client=docling)

        assert result["failed"] == 1
        docling.convert.assert_not_called()

    def test_nested_docling_file_preserves_structure(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline
        db, owner, folders, source, input_dir = pipeline_env

        sub = source / "sub"
        sub.mkdir()
        pdf = sub / "deep.pdf"
        pdf.write_bytes(b"%PDF")

        docling = _make_docling_client("# Deep")
        run_pipeline(db, folders, owner.id, input_dir, docling_client=docling)

        dest = input_dir / "docs" / "sub" / "deep.md"
        assert dest.exists()
