from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.llm_client import LLMClient, LLMError
from app.models import Chunk, PipelineSettings, TranslationSettings

_DEFAULT_PROMPT_PT = "Translate the following text to Portuguese (Brazil). Output only the translation, no preamble:\n\n{text}"
_DEFAULT_PROMPT_EN = "Translate the following text to English. Output only the translation, no preamble:\n\n{text}"


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
    ts = db.query(TranslationSettings).first()
    pipeline_cfg = db.query(PipelineSettings).first()
    effective_max_retries = max_retries if max_retries is not None else (
        pipeline_cfg.max_translation_retries if pipeline_cfg else 3
    )
    batch_size = ts.batch_size if ts else 5
    model = ts.model if ts else ""
    enabled = ts.enabled if ts else False
    prompt_pt = (ts.prompt_template_pt if ts else None) or _DEFAULT_PROMPT_PT
    prompt_en = (ts.prompt_template_en if ts else None) or _DEFAULT_PROMPT_EN

    pending = (
        db.query(Chunk)
        .filter(Chunk.translation_status == "pending")
        .limit(batch_size)
        .all()
    )

    translated = failed = 0
    client = LLMClient(model, ollama_host=ollama_host, openrouter_api_key=openrouter_api_key) if (enabled and model) else None

    for chunk in pending:
        is_en = chunk.source_language == "en"

        if client is None:
            # No translation: copy original to native field, leave other empty
            if is_en:
                chunk.content_en = chunk.content_original
                chunk.content_pt = ""
            else:
                chunk.content_pt = chunk.content_original
                chunk.content_en = ""
            chunk.translation_status = "done"
            chunk.updated_at = datetime.now(timezone.utc)
            translated += 1
        else:
            # Translate to opposite language
            prompt = prompt_pt if is_en else prompt_en
            result = _translate_with_retry(client, chunk.content_original, prompt, effective_max_retries)

            if result is None:
                chunk.translation_status = "failed"
                chunk.translation_error = f"Failed after {effective_max_retries} retries"
                chunk.updated_at = datetime.now(timezone.utc)
                failed += 1
            else:
                if is_en:
                    chunk.content_en = chunk.content_original
                    chunk.content_pt = result
                else:
                    chunk.content_pt = chunk.content_original
                    chunk.content_en = result
                chunk.translation_status = "done"
                chunk.translation_model = model
                chunk.translated_at = datetime.now(timezone.utc)
                chunk.translation_error = None
                chunk.updated_at = datetime.now(timezone.utc)
                translated += 1
        db.commit()

    return {"translated": translated, "failed": failed}


def _translate_with_retry(client: LLMClient, text: str, prompt: str, max_retries: int) -> str | None:
    for _ in range(max_retries):
        try:
            return client.translate(text, prompt_template=prompt)
        except LLMError:
            pass
    return None
