import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "portuguese_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "portuguese_stop", "portuguese_stemmer"],
                },
                "english_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "english_stop", "english_stemmer"],
                },
            },
            "filter": {
                "portuguese_stop": {"type": "stop", "language": "portuguese"},
                "portuguese_stemmer": {"type": "stemmer", "language": "portuguese"},
                "english_stop": {"type": "stop", "language": "english"},
                "english_stemmer": {"type": "stemmer", "language": "english"},
            },
        },
    },
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "file_id": {"type": "keyword"},
            "filename": {"type": "keyword"},
            "domain": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "source_language": {"type": "keyword"},
            "content_pt": {
                "type": "text",
                "analyzer": "portuguese_analyzer",
                "term_vector": "with_positions_offsets",
            },
            "content_en": {
                "type": "text",
                "analyzer": "english_analyzer",
                "term_vector": "with_positions_offsets",
            },
            "indexed_at": {"type": "date"},
        }
    },
}


class OpenSearchError(Exception):
    pass


class OpenSearchClient:
    def __init__(self, host: str, index_prefix: str = "rag", timeout: float = 30.0):
        self._host = host.rstrip("/")
        self._prefix = index_prefix
        self._timeout = timeout

    def _index_name(self, domain: str) -> str:
        return f"{self._prefix}_{domain}"

    def ensure_index(self, domain: str) -> bool:
        """Create index with mapping if it doesn't exist. Idempotent."""
        index = self._index_name(domain)
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.head(f"{self._host}/{index}")
            if resp.status_code == 200:
                return True
            resp = client.put(f"{self._host}/{index}", json=_INDEX_MAPPING)
            resp.raise_for_status()
        logger.info("Created OpenSearch index %s", index)
        return True

    def bulk_index(
        self, domain: str, docs: list[dict[str, Any]]
    ) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        """Bulk index docs. Returns (successes, errors) as (chunk_id, os_id/error_msg)."""
        index = self._index_name(domain)
        lines: list[str] = []
        chunk_ids: list[str] = []
        for doc in docs:
            chunk_id = doc["chunk_id"]
            chunk_ids.append(chunk_id)
            lines.append(f'{{"index": {{"_index": "{index}"}}}}')
            lines.append(_json_line(doc))
        body = "\n".join(lines) + "\n"

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._host}/_bulk",
                content=body,
                headers={"Content-Type": "application/x-ndjson"},
            )
            resp.raise_for_status()
            data = resp.json()

        successes: list[tuple[str, str]] = []
        errors: list[tuple[str, str]] = []
        for chunk_id, item in zip(chunk_ids, data["items"]):
            action = item.get("index", {})
            if action.get("status", 0) in (200, 201):
                successes.append((chunk_id, action["_id"]))
            else:
                reason = action.get("error", {}).get("reason", "unknown error")
                errors.append((chunk_id, reason))
        return successes, errors

    def bulk_delete(self, domain: str, opensearch_ids: list[str]) -> list[str]:
        """Bulk delete by OpenSearch _id. Returns list of confirmed deleted ids."""
        index = self._index_name(domain)
        lines: list[str] = []
        for os_id in opensearch_ids:
            lines.append(f'{{"delete": {{"_index": "{index}", "_id": "{os_id}"}}}}')
        body = "\n".join(lines) + "\n"

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._host}/_bulk",
                content=body,
                headers={"Content-Type": "application/x-ndjson"},
            )
            resp.raise_for_status()
            data = resp.json()

        confirmed: list[str] = []
        for item in data["items"]:
            action = item.get("delete", {})
            if action.get("status", 0) in (200, 201):
                confirmed.append(action["_id"])
        return confirmed

    def search(
        self,
        query: str,
        domain: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict:
        """BM25 multi_match search across content_pt and content_en with highlights."""
        index = self._index_name(domain) if domain else f"{self._prefix}_*"
        body = {
            "from": offset,
            "size": limit,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["content_pt", "content_en"],
                    "type": "best_fields",
                    "operator": "or",
                }
            },
            "highlight": {
                "fields": {"content_pt": {}, "content_en": {}}
            },
        }

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(f"{self._host}/{index}/_search", json=body)
            resp.raise_for_status()
            data = resp.json()

        hits_raw = data["hits"]["hits"]
        hits = []
        for h in hits_raw:
            source = h.get("_source", {})
            highlight_parts = []
            for field_snippets in h.get("highlight", {}).values():
                highlight_parts.extend(field_snippets)
            hits.append(
                {
                    "chunk_id": source.get("chunk_id"),
                    "file_id": source.get("file_id"),
                    "filename": source.get("filename"),
                    "domain": source.get("domain"),
                    "chunk_index": source.get("chunk_index"),
                    "highlight": " … ".join(highlight_parts),
                    "score": h.get("_score"),
                }
            )
        return {
            "total": data["hits"]["total"]["value"],
            "hits": hits,
        }

    def get_index_stats(self, domain: str) -> dict:
        """Return {docs_count, index_size_mb} for a domain index."""
        index = self._index_name(domain)
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(f"{self._host}/{index}/_stats")
            if resp.status_code == 404:
                return {"docs_count": 0, "index_size_mb": 0.0}
            resp.raise_for_status()
            data = resp.json()

        index_data = data.get("indices", {}).get(index, {})
        primaries = index_data.get("primaries", {})
        docs_count = primaries.get("docs", {}).get("count", 0)
        size_bytes = primaries.get("store", {}).get("size_in_bytes", 0)
        return {
            "docs_count": docs_count,
            "index_size_mb": round(size_bytes / (1024 * 1024), 2),
        }

    def forcemerge(self, domain: str, max_num_segments: int = 1) -> None:
        """Force merge index segments for a domain to optimize search performance."""
        index = self._index_name(domain)
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._host}/{index}/_forcemerge",
                params={"max_num_segments": max_num_segments},
            )
            resp.raise_for_status()


def _json_line(obj: dict) -> str:
    import json
    return json.dumps(obj, default=str)
