from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from langdetect import DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException
from sqlalchemy.orm import Session

from app.models import Chunk, File, PipelineSettings

DetectorFactory.seed = 0  # deterministic results

_LANG_THRESHOLD = 0.80
_MIN_CHUNK_CHARS = 50


def detect_language(text: str) -> str:
    if not text or len(text.strip()) < 10:
        return "unknown"
    start = len(text) // 4
    end = len(text) * 3 // 4
    sample = text[start:end][:2000]
    if not sample.strip():
        return "unknown"
    try:
        probs = detect_langs(sample)
        top = probs[0]
        if top.prob >= _LANG_THRESHOLD and top.lang in ("pt", "en"):
            return top.lang
        return "unknown"
    except LangDetectException:
        return "unknown"


def chunk_text(text: str, size: int = 1000, overlap: int = 100) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        if end >= len(text):
            piece = text[start:].strip()
            if len(piece) >= _MIN_CHUNK_CHARS:
                chunks.append(piece)
            break
        # prefer splitting at double newline
        split_pos = _find_split(text, start, end, "\n\n")
        if split_pos is None:
            # fall back to sentence boundary
            split_pos = _find_split(text, start, end, ".")
        if split_pos is None:
            # fall back to word boundary
            split_pos = _rfind_space(text, start, end)
        if split_pos is None:
            split_pos = end

        piece = text[start:split_pos].strip()
        if len(piece) >= _MIN_CHUNK_CHARS:
            chunks.append(piece)
        # move start back by overlap
        start = max(start + 1, split_pos - overlap)
    return chunks


def _find_split(text: str, start: int, end: int, sep: str) -> int | None:
    pos = text.rfind(sep, start, end)
    if pos == -1 or pos <= start:
        return None
    return pos + len(sep)


def _rfind_space(text: str, start: int, end: int) -> int | None:
    pos = text.rfind(" ", start, end)
    if pos == -1 or pos <= start:
        return None
    return pos + 1


def _read_file(path: str, docling_base_url: str) -> str:
    from app.pipeline.router import route
    kind = route(path)
    if kind == "unsupported":
        raise ValueError(f"Unsupported file type: {path}")
    if kind == "direct":
        return Path(path).read_text(errors="replace")
    if kind == "pdf_direct":
        from app.pdf_direct import convert_to_markdown
        return convert_to_markdown(path)
    if kind == "markitdown":
        from app.markitdown_client import convert_to_markdown
        return convert_to_markdown(path)
    if kind == "docling":
        if not docling_base_url:
            raise ValueError("Docling required but DOCLING_BASE_URL not configured")
        from app.docling_client import DoclingClient
        return DoclingClient(docling_base_url).convert(path)
    raise ValueError(f"Unknown route kind: {kind}")


def run_parse_job() -> None:
    """Standalone scheduler wrapper — manages its own DB session."""
    import logging
    from app.config import Settings
    from app.database import get_engine, get_session_factory

    logger = logging.getLogger(__name__)
    settings = Settings()
    engine = get_engine(settings.database_url)
    factory = get_session_factory(engine)
    db = factory()
    try:
        run_parse(db, docling_base_url=settings.docling_base_url)
    except Exception as exc:
        logger.error("Scheduled parse job failed: %s", exc)
    finally:
        db.close()
        engine.dispose()


def run_parse(db: Session, docling_base_url: str = "") -> dict:
    pipeline_cfg = db.query(PipelineSettings).first()
    chunk_size = pipeline_cfg.chunk_size if pipeline_cfg else 1000
    chunk_overlap = pipeline_cfg.chunk_overlap if pipeline_cfg else 100
    batch_size = pipeline_cfg.parse_batch_size if pipeline_cfg else 20

    files = (
        db.query(File)
        .filter(File.parse_status.in_(["pending", "processing"]), File.deleted_at.is_(None))
        .limit(batch_size)
        .all()
    )
    processed = failed = 0
    for file_row in files:
        file_row.parse_status = "processing"
        file_row.updated_at = datetime.now(timezone.utc)
        db.commit()
        try:
            text = _read_file(file_row.path, docling_base_url)
            raw_chunks = chunk_text(text, size=chunk_size, overlap=chunk_overlap)
            lang = detect_language(text)
            translation_status = "pending"
            for idx, content in enumerate(raw_chunks):
                chunk = Chunk(
                    file_id=file_row.id,
                    chunk_index=idx,
                    content_original=content,
                    source_language=lang,
                    char_count=len(content),
                    translation_status=translation_status,
                )
                db.add(chunk)
            file_row.parse_status = "done"
            file_row.parse_error = None
            file_row.updated_at = datetime.now(timezone.utc)
            db.commit()
            processed += 1
        except Exception as exc:
            db.rollback()
            file_row.parse_status = "failed"
            file_row.parse_error = str(exc)
            file_row.updated_at = datetime.now(timezone.utc)
            db.commit()
            failed += 1
    return {"processed": processed, "failed": failed}
