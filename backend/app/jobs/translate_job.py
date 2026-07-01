from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import NamedTuple
import uuid

from sqlalchemy.orm import Session

from app.llm_client import LLMClient, LLMError
from app.models import Chunk, PipelineSettings, TranslationSettings

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT_PT = "Translate the following text to Portuguese (Brazil). Output only the translation, no preamble:\n\n{text}"
_DEFAULT_PROMPT_EN = "Translate the following text to English. Output only the translation, no preamble:\n\n{text}"

_MAX_WORKERS = 10


class _ChunkData(NamedTuple):
    chunk_id: uuid.UUID
    is_en: bool
    original: str
    prompt: str


class _TranslateResult(NamedTuple):
    chunk_id: uuid.UUID
    is_en: bool
    translation: str | None  # None = failed
    original: str
    error: str | None


def run_translate_job() -> None:
    """Standalone scheduler wrapper — manages its own DB session."""
    from app.config import Settings
    from app.database import get_engine, get_session_factory

    settings = Settings()
    engine = get_engine(settings.database_url)
    factory = get_session_factory(engine)
    db = factory()
    try:
        result = run_translate(
            db,
            ollama_host=settings.ollama_host,
            openrouter_api_key=settings.openrouter_api_key,
            max_workers=settings.translate_workers,
        )
        logger.info("translate_job completed: translated=%d failed=%d", result["translated"], result["failed"])
    except Exception as exc:
        logger.error("translate_job failed: %s", exc, exc_info=True)
    finally:
        db.close()
        engine.dispose()


def run_translate(
    db: Session,
    ollama_host: str = "http://host.docker.internal:11434",
    openrouter_api_key: str = "",
    max_retries: int | None = None,
    max_workers: int = _MAX_WORKERS,
) -> dict:
    ts = db.query(TranslationSettings).first()
    pipeline_cfg = db.query(PipelineSettings).first()
    effective_max_retries = max_retries if max_retries is not None else (
        pipeline_cfg.max_translation_retries if pipeline_cfg else 3
    )
    batch_size = ts.batch_size if ts else 200
    model = ts.model if ts else ""
    enabled = ts.enabled if ts else False
    prompt_pt = (ts.prompt_template_pt if ts else None) or _DEFAULT_PROMPT_PT
    prompt_en = (ts.prompt_template_en if ts else None) or _DEFAULT_PROMPT_EN
    effective_workers = max_workers if ts is None else ts.translate_workers

    pending = (
        db.query(Chunk)
        .filter(Chunk.translation_status == "pending")
        .limit(batch_size)
        .all()
    )

    if not pending:
        return {"translated": 0, "failed": 0}

    # Extract all needed data into plain Python types, then close the read
    # transaction. This prevents idle-in-transaction timeouts while HTTP
    # calls are in flight (which can take 30-60s for a full batch).
    jobs: list[_ChunkData] = [
        _ChunkData(
            chunk_id=c.id,
            is_en=c.source_language == "en",
            original=c.content_original,
            prompt=prompt_pt if c.source_language == "en" else prompt_en,
        )
        for c in pending
    ]
    db.commit()  # close read transaction; connections return to pool

    client = LLMClient(model, ollama_host=ollama_host, openrouter_api_key=openrouter_api_key) if (enabled and model) else None
    now = datetime.now(timezone.utc)
    translated = failed = 0

    if client is None:
        # No LLM — copy original to native field, leave other empty
        for j in jobs:
            chunk = db.get(Chunk, j.chunk_id)
            if chunk is None:
                continue
            if j.is_en:
                chunk.content_en = j.original
                chunk.content_pt = ""
            else:
                chunk.content_pt = j.original
                chunk.content_en = ""
            chunk.translation_status = "done"
            chunk.updated_at = now
            translated += 1
        db.commit()
        logger.info("translate_job (no-LLM): copied %d chunks", translated)
        return {"translated": translated, "failed": failed}

    logger.info("translate_job: starting %d chunks with %d workers", len(jobs), effective_workers)

    # HTTP call timeout + retry headroom (per future, not per batch)
    _FUTURE_TIMEOUT = 150.0  # slightly above httpx timeout of 120s

    # Parallel HTTP calls — DB session NOT touched inside threads.
    # Write + commit each result as it arrives so progress is visible
    # immediately and completed work is not lost if the job is interrupted.
    with ThreadPoolExecutor(max_workers=effective_workers) as executor:
        future_map = {
            executor.submit(
                _translate_with_retry, client, j.original, j.prompt, effective_max_retries
            ): j
            for j in jobs
        }
        for future in as_completed(future_map, timeout=_FUTURE_TIMEOUT * len(jobs)):
            j = future_map[future]
            try:
                text = future.result(timeout=_FUTURE_TIMEOUT)
            except Exception as exc:
                logger.warning("translate_job: chunk %s raised %s", j.chunk_id, exc)
                text = None
                error = str(exc)
            else:
                error = None if text is not None else f"Failed after {effective_max_retries} retries"
                if text is None:
                    logger.warning("translate_job: chunk %s failed after %d retries", j.chunk_id, effective_max_retries)

            chunk = db.get(Chunk, j.chunk_id)
            if chunk is None:
                continue
            if text is None:
                chunk.translation_status = "failed"
                chunk.translation_error = error
                chunk.updated_at = now
                failed += 1
            else:
                if j.is_en:
                    chunk.content_en = j.original
                    chunk.content_pt = text
                else:
                    chunk.content_pt = j.original
                    chunk.content_en = text
                chunk.translation_status = "done"
                chunk.translation_model = model
                chunk.translated_at = now
                chunk.translation_error = None
                chunk.index_status = "pending"
                chunk.updated_at = now
                translated += 1
            db.commit()

    logger.info("translate_job: completed translated=%d failed=%d", translated, failed)
    return {"translated": translated, "failed": failed}


def _translate_with_retry(client: LLMClient, text: str, prompt: str, max_retries: int) -> str | None:
    for attempt in range(max_retries):
        try:
            return client.translate(text, prompt_template=prompt)
        except LLMError as exc:
            logger.debug("_translate_with_retry: attempt %d/%d failed: %s", attempt + 1, max_retries, exc)
    return None
