import pytest
from unittest.mock import patch, MagicMock


pytestmark = pytest.mark.integration


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


class TestPdfDirectRoute:
    def test_digital_pdf_converted_and_saved_as_md(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline

        db, owner, folders, source, input_dir = pipeline_env
        pdf = source / "report.pdf"
        pdf.write_bytes(b"fake")

        with patch("app.pipeline.router.is_digital_pdf", return_value=True), \
             patch("app.pipeline.ingestor.pdf_direct_convert", return_value="# Report\n\nContent."):
            result = run_pipeline(db, folders, owner.id, input_dir)

        assert result["processed"] == 1
        dest = input_dir / "docs" / "report.md"
        assert dest.exists()
        assert dest.read_text() == "# Report\n\nContent."

    def test_digital_pdf_route_recorded(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline
        from app.models import ProcessedFile

        db, owner, folders, source, input_dir = pipeline_env
        pdf = source / "digital.pdf"
        pdf.write_bytes(b"fake")

        with patch("app.pipeline.router.is_digital_pdf", return_value=True), \
             patch("app.pipeline.ingestor.pdf_direct_convert", return_value="# Content"):
            run_pipeline(db, folders, owner.id, input_dir)

        pf = db.query(ProcessedFile).filter(ProcessedFile.source_path == str(pdf)).first()
        assert pf.route == "pdf_direct"
        assert pf.status == "done"

    def test_pdf_direct_error_marks_failed_batch_continues(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline

        db, owner, folders, source, input_dir = pipeline_env
        (source / "bad.pdf").write_bytes(b"fake")
        (source / "good.md").write_text("good")

        with patch("app.pipeline.router.is_digital_pdf", return_value=True), \
             patch("app.pipeline.ingestor.pdf_direct_convert", side_effect=RuntimeError("mupdf error")):
            result = run_pipeline(db, folders, owner.id, input_dir)

        assert result["failed"] == 1
        assert result["processed"] == 1

    def test_dedup_applies_to_pdf_direct_route(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline

        db, owner, folders, source, input_dir = pipeline_env
        pdf = source / "dup.pdf"
        pdf.write_bytes(b"digital content")

        with patch("app.pipeline.router.is_digital_pdf", return_value=True), \
             patch("app.pipeline.ingestor.pdf_direct_convert", return_value="# Dup") as mock_conv:
            run_pipeline(db, folders, owner.id, input_dir)
            result2 = run_pipeline(db, folders, owner.id, input_dir)

        assert result2["skipped"] == 1
        assert mock_conv.call_count == 1

    def test_nested_pdf_direct_preserves_structure(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline

        db, owner, folders, source, input_dir = pipeline_env
        sub = source / "sub"
        sub.mkdir()
        pdf = sub / "deep.pdf"
        pdf.write_bytes(b"fake")

        with patch("app.pipeline.router.is_digital_pdf", return_value=True), \
             patch("app.pipeline.ingestor.pdf_direct_convert", return_value="# Deep"):
            run_pipeline(db, folders, owner.id, input_dir)

        assert (input_dir / "docs" / "sub" / "deep.md").exists()


class TestMarkitdownRoute:
    def test_docx_converted_and_saved_as_md(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline

        db, owner, folders, source, input_dir = pipeline_env
        docx = source / "slides.docx"
        docx.write_bytes(b"PK fake")

        with patch("app.pipeline.ingestor.markitdown_convert", return_value="# Slides"):
            result = run_pipeline(db, folders, owner.id, input_dir)

        assert result["processed"] == 1
        assert (input_dir / "docs" / "slides.md").exists()

    def test_html_converted_via_markitdown(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline

        db, owner, folders, source, input_dir = pipeline_env
        html = source / "page.html"
        html.write_text("<h1>Hello</h1>")

        with patch("app.pipeline.ingestor.markitdown_convert", return_value="# Hello"):
            result = run_pipeline(db, folders, owner.id, input_dir)

        assert result["processed"] == 1
        assert (input_dir / "docs" / "page.md").exists()

    def test_markitdown_route_recorded(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline
        from app.models import ProcessedFile

        db, owner, folders, source, input_dir = pipeline_env
        docx = source / "doc.docx"
        docx.write_bytes(b"fake")

        with patch("app.pipeline.ingestor.markitdown_convert", return_value="# Doc"):
            run_pipeline(db, folders, owner.id, input_dir)

        pf = db.query(ProcessedFile).filter(ProcessedFile.source_path == str(docx)).first()
        assert pf.route == "markitdown"
        assert pf.status == "done"

    def test_markitdown_error_marks_failed_batch_continues(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline

        db, owner, folders, source, input_dir = pipeline_env
        (source / "bad.docx").write_bytes(b"fake")
        (source / "good.md").write_text("good")

        with patch("app.pipeline.ingestor.markitdown_convert", side_effect=RuntimeError("parse error")):
            result = run_pipeline(db, folders, owner.id, input_dir)

        assert result["failed"] == 1
        assert result["processed"] == 1

    def test_dedup_applies_to_markitdown_route(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline

        db, owner, folders, source, input_dir = pipeline_env
        docx = source / "dup.docx"
        docx.write_bytes(b"docx content")

        with patch("app.pipeline.ingestor.markitdown_convert", return_value="# Dup") as mock_conv:
            run_pipeline(db, folders, owner.id, input_dir)
            result2 = run_pipeline(db, folders, owner.id, input_dir)

        assert result2["skipped"] == 1
        assert mock_conv.call_count == 1


class TestUnsupportedRoute:
    def test_unsupported_extension_marks_failed(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline

        db, owner, folders, source, input_dir = pipeline_env
        (source / "file.xyz").write_text("unknown")

        result = run_pipeline(db, folders, owner.id, input_dir)

        assert result["failed"] == 1

    def test_unsupported_does_not_stop_batch(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline

        db, owner, folders, source, input_dir = pipeline_env
        (source / "bad.xyz").write_text("unknown")
        (source / "good.md").write_text("good")

        result = run_pipeline(db, folders, owner.id, input_dir)

        assert result["failed"] == 1
        assert result["processed"] == 1

    def test_unsupported_route_recorded(self, pipeline_env):
        from app.pipeline.ingestor import run_pipeline
        from app.models import ProcessedFile

        db, owner, folders, source, input_dir = pipeline_env
        f = source / "file.xyz"
        f.write_text("unknown")
        run_pipeline(db, folders, owner.id, input_dir)

        pf = db.query(ProcessedFile).filter(ProcessedFile.source_path == str(f)).first()
        assert pf.status == "failed"
        assert pf.route == "unsupported"
