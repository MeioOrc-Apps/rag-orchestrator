from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.llm_client import LLMClient, LLMError
from app.models import Chunk, TranslationSettings


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
        run_translate(db)
    except Exception as exc:
        logger.error("Scheduled translate job failed: %s", exc)
    finally:
        db.close()
        engine.dispose()


def run_translate(db: Session, max_retries: int | None = None) -> dict:
    settings = db.query(TranslationSettings).filter(TranslationSettings.enabled.is_(True)).first()
    if settings is None:
        return {"translated": 0, "failed": 0, "skipped": 0}

    from app.config import Settings as AppSettings
    app_cfg = AppSettings()
    effective_max_retries = max_retries if max_retries is not None else app_cfg.max_translation_retries

    # Handle not_needed: copy original → content_en, mark done (no LLM)
    not_needed = (
        db.query(Chunk)
        .filter(Chunk.translation_status == "not_needed", Chunk.content_en.is_(None))
        .limit(settings.batch_size)
        .all()
    )
    skipped = 0
    for chunk in not_needed:
        chunk.content_en = chunk.content_original
        chunk.translation_status = "done"
        chunk.updated_at = datetime.now(timezone.utc)
        skipped += 1
    if not_needed:
        db.commit()

    # Handle pending: translate via LLM
    pending = (
        db.query(Chunk)
        .filter(Chunk.translation_status == "pending")
        .limit(settings.batch_size)
        .all()
    )
    translated = failed = 0
    if pending:
        client = LLMClient(settings.model, ollama_host=app_cfg.ollama_host)
    for chunk in pending:
        result = _translate_with_retry(client, chunk.content_original, settings, effective_max_retries)
        if result is None:
            chunk.translation_status = "failed"
            chunk.translation_error = f"Failed after {effective_max_retries} retries"
            chunk.updated_at = datetime.now(timezone.utc)
            failed += 1
        else:
            chunk.content_en = result
            chunk.translation_status = "done"
            chunk.translation_model = settings.model
            chunk.translated_at = datetime.now(timezone.utc)
            chunk.translation_error = None
            chunk.updated_at = datetime.now(timezone.utc)
            translated += 1
        db.commit()

    return {"translated": translated, "failed": failed, "skipped": skipped}


def _translate_with_retry(
    client: LLMClient, text: str, settings: TranslationSettings, max_retries: int
) -> str | None:
    last_error: Exception | None = None
    for _ in range(max_retries):
        try:
            return client.translate(text, prompt_template=settings.prompt_template)
        except LLMError as exc:
            last_error = exc
    return None
