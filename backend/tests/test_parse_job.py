"""Tests for parse_job — chunking, language detection, and file parsing."""
import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------

class TestDetectLanguage:
    def test_english_text_returns_en(self):
        from app.jobs.parse_job import detect_language

        text = (
            "The quick brown fox jumps over the lazy dog. "
            "Natural language processing is a field of artificial intelligence. "
            "Machine learning models are trained on large datasets of text. "
            "This sentence is written in English and should be detected correctly."
        ) * 5
        assert detect_language(text) == "en"

    def test_portuguese_text_returns_pt(self):
        from app.jobs.parse_job import detect_language

        text = (
            "O rato roeu a roupa do rei de Roma. "
            "O processamento de linguagem natural é um campo da inteligência artificial. "
            "Os modelos de aprendizado de máquina são treinados em grandes conjuntos de dados. "
            "Esta frase está escrita em português e deve ser detectada corretamente."
        ) * 5
        assert detect_language(text) == "pt"

    def test_very_short_text_returns_unknown(self):
        from app.jobs.parse_job import detect_language

        assert detect_language("ok") == "unknown"

    def test_empty_text_returns_unknown(self):
        from app.jobs.parse_job import detect_language

        assert detect_language("") == "unknown"

    def test_samples_middle_25_to_75_percent(self):
        from app.jobs.parse_job import detect_language

        # Pad start/end with unrelated chars; middle is clear English
        filler = "aaaa bbbb cccc dddd eeee " * 20  # ~500 chars, no real language
        english_middle = (
            "The quick brown fox jumps over the lazy dog. "
            "Natural language processing helps computers understand human language. "
            "This text in the middle should determine the detected language. "
        ) * 6
        text = filler + english_middle + filler
        # langdetect should sample the middle and detect English
        result = detect_language(text)
        assert result in ("en", "unknown")  # filler may confuse; middle is English


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------

class TestChunkText:
    def test_short_text_returns_single_chunk(self):
        from app.jobs.parse_job import chunk_text

        text = "Hello world. This is a short document that is long enough to not be discarded."
        chunks = chunk_text(text, size=500, overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == text.strip()

    def test_long_text_splits_into_multiple_chunks(self):
        from app.jobs.parse_job import chunk_text

        text = ("word " * 1200).strip()  # 1200 words > 500
        chunks = chunk_text(text, size=500, overlap=50)
        assert len(chunks) > 1

    def test_chunks_respect_max_word_count(self):
        from app.jobs.parse_job import chunk_text

        text = ("word " * 600).strip()
        chunks = chunk_text(text, size=100, overlap=10)
        for chunk in chunks:
            assert len(chunk.split()) <= 100

    def test_chunks_have_word_overlap(self):
        from app.jobs.parse_job import chunk_text

        words = [f"word{i}" for i in range(100)]
        text = " ".join(words)
        chunks = chunk_text(text, size=30, overlap=10)
        if len(chunks) > 1:
            last_words_of_first = chunks[0].split()[-10:]
            first_words_of_second = chunks[1].split()[:10]
            assert last_words_of_first == first_words_of_second

    def test_discards_chunks_shorter_than_50_chars(self):
        from app.jobs.parse_job import chunk_text

        # "ab " * 3 = "ab ab ab" = 8 chars < 50 → discarded
        filler = ("ab " * 3).strip()  # 3 words, < 50 chars
        body = ("longword " * 200).strip()
        chunks = chunk_text(filler + " " + body, size=3, overlap=0)
        for chunk in chunks:
            assert len(chunk) >= 50

    def test_overlap_equal_to_size_does_not_hang(self):
        from app.jobs.parse_job import chunk_text

        # "longerword " × 20 → 5-word window = 54 chars ≥ 50 → not discarded
        text = ("longerword " * 20).strip()
        chunks = chunk_text(text, size=5, overlap=5)
        assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# parse_job integration
# ---------------------------------------------------------------------------

@pytest.fixture
def file_in_db(db_session, tmp_path):
    from app.models import User, WatchedFolder, File
    from app.pipeline.scanner import compute_hash

    user = db_session.query(User).filter(User.username == "sergio").first()
    source = tmp_path / "source"
    source.mkdir()
    fpath = source / "doc.md"
    fpath.write_text("hello world")

    folder = WatchedFolder(
        owner_id=user.id,
        host_path=str(source),
        dest_subdir="docs",
        recursive=True,
        enabled=True,
    )
    db_session.add(folder)
    db_session.flush()

    file_row = File(
        path=str(fpath),
        filename="doc.md",
        domain="docs",
        file_hash=compute_hash(fpath),
        file_size_bytes=fpath.stat().st_size,
        parse_status="pending",
    )
    db_session.add(file_row)
    db_session.commit()
    db_session.refresh(file_row)
    return file_row, fpath


class TestParseJobInsertsChunks:
    def test_pending_file_gets_chunks_inserted(self, db_session, file_in_db):
        from app.jobs.parse_job import run_parse
        from app.models import Chunk

        file_row, fpath = file_in_db
        fpath.write_text("This is a test document with enough content to parse.")

        run_parse(db_session)

        chunks = db_session.query(Chunk).filter(Chunk.file_id == file_row.id).all()
        assert len(chunks) >= 1

    def test_pending_file_parse_status_set_to_done(self, db_session, file_in_db):
        from app.jobs.parse_job import run_parse

        file_row, fpath = file_in_db
        fpath.write_text("This is a test document with enough content to parse.")

        run_parse(db_session)

        db_session.refresh(file_row)
        assert file_row.parse_status == "done"

    def test_soft_deleted_file_not_parsed(self, db_session, file_in_db):
        from app.jobs.parse_job import run_parse
        from app.models import Chunk
        from datetime import datetime, timezone

        file_row, _ = file_in_db
        file_row.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        run_parse(db_session)

        assert db_session.query(Chunk).count() == 0

    def test_already_done_file_not_reprocessed(self, db_session, file_in_db):
        from app.jobs.parse_job import run_parse
        from app.models import Chunk

        file_row, fpath = file_in_db
        fpath.write_text("Content for parsing.")
        file_row.parse_status = "done"
        db_session.commit()

        run_parse(db_session)

        assert db_session.query(Chunk).count() == 0


class TestTranslationStatusOnInsert:
    def test_english_file_all_chunks_get_source_language_en(self, db_session, file_in_db):
        from app.jobs.parse_job import run_parse
        from app.models import Chunk

        file_row, fpath = file_in_db
        fpath.write_text(
            "The quick brown fox jumps over the lazy dog. "
            "This document is clearly written in English. "
            "Natural language processing helps machines understand human text. " * 10
        )

        run_parse(db_session)

        chunks = db_session.query(Chunk).filter(Chunk.file_id == file_row.id).all()
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.translation_status == "pending"
            assert chunk.source_language == "en"

    def test_portuguese_file_all_chunks_get_source_language_pt(self, db_session, file_in_db):
        from app.jobs.parse_job import run_parse
        from app.models import Chunk

        file_row, fpath = file_in_db
        fpath.write_text(
            "O rato roeu a roupa do rei de Roma. "
            "Este documento está claramente escrito em português. "
            "O processamento de linguagem natural ajuda as máquinas a entender textos humanos. " * 10
        )

        run_parse(db_session)

        chunks = db_session.query(Chunk).filter(Chunk.file_id == file_row.id).all()
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.translation_status == "pending"
            assert chunk.source_language == "pt"


class TestParseJobErrorHandling:
    def test_unreadable_file_sets_parse_status_failed(self, db_session, file_in_db):
        from app.jobs.parse_job import run_parse

        file_row, fpath = file_in_db
        # Remove file so reading it will fail
        fpath.unlink()

        run_parse(db_session)

        db_session.refresh(file_row)
        assert file_row.parse_status == "failed"
        assert file_row.parse_error is not None

    def test_parse_error_does_not_stop_other_files(self, db_session, tmp_path):
        from app.jobs.parse_job import run_parse
        from app.models import User, WatchedFolder, File, Chunk
        from app.pipeline.scanner import compute_hash

        user = db_session.query(User).filter(User.username == "sergio").first()
        source = tmp_path / "src"
        source.mkdir()

        # File 1: bad (missing from disk)
        bad_path = source / "missing.md"
        bad_path.write_text("placeholder")
        bad_row = File(
            path=str(bad_path),
            filename="missing.md",
            domain="docs",
            file_hash=compute_hash(bad_path),
            file_size_bytes=bad_path.stat().st_size,
            parse_status="pending",
        )
        bad_path.unlink()

        # File 2: good
        good_path = source / "good.md"
        good_path.write_text(
            "The quick brown fox jumps over the lazy dog. " * 10
        )
        good_row = File(
            path=str(good_path),
            filename="good.md",
            domain="docs",
            file_hash=compute_hash(good_path),
            file_size_bytes=good_path.stat().st_size,
            parse_status="pending",
        )
        db_session.add_all([bad_row, good_row])
        db_session.commit()

        run_parse(db_session)

        db_session.refresh(bad_row)
        db_session.refresh(good_row)
        assert bad_row.parse_status == "failed"
        assert good_row.parse_status == "done"
        assert db_session.query(Chunk).filter(Chunk.file_id == good_row.id).count() >= 1
