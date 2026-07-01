from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.llm_client import LLMClient, LLMError
from app.models import Chunk, PipelineSettings, TranslationSettings


def run_translate_job() -> None:
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
        run_translate(db, ollama_host=settings.ollama_host, openrouter_api_key=settings.openrouter_api_key)
    except Exception as exc:
        logger.error("Scheduled translate job failed: %s", exc)
    finally:
        db.close()
        engine.dispose()


def run_translate(
    db: Session,
    ollama_host: str = "http://host.docker.internal:11434",
    openrouter_api_key: str = "",
    max_retries: int | None = None,
) -> dict:
    ts = db.query(TranslationSettings).filter(TranslationSettings.enabled.is_(True)).first()
    if ts is None or not ts.model:
        # Translation disabled or no model configured — still handle not_needed chunks
        return _copy_not_needed(db)

    pipeline_cfg = db.query(PipelineSettings).first()
    effective_max_retries = max_retries if max_retries is not None else (
        pipeline_cfg.max_translation_retries if pipeline_cfg else 3
    )

    # Handle not_needed: copy original → content_en, mark done (no LLM)
    result = _copy_not_needed(db, batch_size=ts.batch_size)
    skipped = result["skipped"]

    # Handle pending: translate via LLM
    pending = (
        db.query(Chunk)
        .filter(Chunk.translation_status == "pending")
        .limit(ts.batch_size)
        .all()
    )
    translated = failed = 0
    if pending:
        client = LLMClient(ts.model, ollama_host=ollama_host, openrouter_api_key=openrouter_api_key)
    for chunk in pending:
        res = _translate_with_retry(client, chunk.content_original, ts, effective_max_retries)
        if res is None:
            chunk.translation_status = "failed"
            chunk.translation_error = f"Failed after {effective_max_retries} retries"
            chunk.updated_at = datetime.now(timezone.utc)
            failed += 1
        else:
            chunk.content_en = res
            chunk.translation_status = "done"
            chunk.translation_model = ts.model
            chunk.translated_at = datetime.now(timezone.utc)
            chunk.translation_error = None
            chunk.updated_at = datetime.now(timezone.utc)
            translated += 1
        db.commit()

    return {"translated": translated, "failed": failed, "skipped": skipped}


def _copy_not_needed(db: Session, batch_size: int = 50) -> dict:
    not_needed = (
        db.query(Chunk)
        .filter(Chunk.translation_status == "not_needed", Chunk.content_en.is_(None))
        .limit(batch_size)
        .all()
    )
    for chunk in not_needed:
        chunk.content_en = chunk.content_original
        chunk.translation_status = "done"
        chunk.updated_at = datetime.now(timezone.utc)
    if not_needed:
        db.commit()
    return {"skipped": len(not_needed)}


def _translate_with_retry(
    client: LLMClient, text: str, settings: TranslationSettings, max_retries: int
) -> str | None:
    for _ in range(max_retries):
        try:
            return client.translate(text, prompt_template=settings.prompt_template)
        except LLMError:
            pass
    return None
