from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.llm_client import LLMClient, LLMError
from app.models import SearchQueryLog, TranslationSettings
from app.opensearch_client import OpenSearchClient
from app.schemas.search import SearchRequest, SearchHit, SearchResponse

router = APIRouter(prefix="/api/search", tags=["search"])


def _get_os_client() -> OpenSearchClient:
    from app.config import Settings
    cfg = Settings()
    return OpenSearchClient(cfg.opensearch_host, index_prefix=cfg.opensearch_index_prefix)


def _hits_from_response(data: dict) -> tuple[list[SearchHit], int]:
    raw_hits = data.get("hits", {}).get("hits", [])
    total = data.get("hits", {}).get("total", {}).get("value", 0)
    hits = []
    for h in raw_hits:
        src = h.get("_source", {})
        hits.append(SearchHit(
            chunk_id=src.get("chunk_id", ""),
            file_id=src.get("file_id", ""),
            domain=src.get("domain", ""),
            chunk_index=src.get("chunk_index", 0),
            source_language=src.get("source_language", ""),
            content_en=src.get("content_en", ""),
            content_pt=src.get("content_pt", ""),
            score=h.get("_score", 0.0),
            highlights=h.get("highlight", {}),
        ))
    return hits, total


@router.post("", response_model=SearchResponse)
def search(req: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    from app.config import Settings
    cfg = Settings()
    client = _get_os_client()

    # Read enrichment config from DB
    ts = db.query(TranslationSettings).first()
    enrichment_model = ts.enrichment_model if ts else ""
    enrichment_prompt = (ts.prompt_enrichment if ts else None) or (
        "Expand this search query with synonyms and related terms for better retrieval. "
        "Output only the expanded query, no explanation:\n\n{text}"
    )

    query_enriched: str | None = None
    fallback_used = False
    latency_start = datetime.now(timezone.utc)

    search_query = req.query
    enrich_attempted = False

    if req.enrich and enrichment_model:
        try:
            llm = LLMClient(enrichment_model, ollama_host=cfg.ollama_host, openrouter_api_key=cfg.openrouter_api_key)
            query_enriched = llm.translate(req.query, prompt_template=enrichment_prompt)
            search_query = query_enriched
            enrich_attempted = True
        except LLMError:
            fallback_used = True

    data = client.search(search_query, domain=req.domain, limit=req.limit, offset=req.offset)
    hits, total = _hits_from_response(data)

    # Fallback: 0 results with enrichment → retry with original
    if total == 0 and enrich_attempted and not fallback_used:
        data = client.search(req.query, domain=req.domain, limit=req.limit, offset=req.offset)
        hits, total = _hits_from_response(data)
        fallback_used = True

    now = datetime.now(timezone.utc)
    latency_ms = int((now - latency_start).total_seconds() * 1000)
    top_score = hits[0].score if hits else None

    log = SearchQueryLog(
        query_original=req.query,
        query_enriched=query_enriched,
        domain_filter=req.domain,
        results_count=total,
        top_score=top_score,
        latency_ms=latency_ms,
        enrichment_used=enrich_attempted and not fallback_used,
        fallback_used=fallback_used,
    )
    db.add(log)
    db.commit()

    return SearchResponse(
        results=hits,
        total=total,
        fallback_used=fallback_used,
        query_enriched=query_enriched if not fallback_used else None,
    )
