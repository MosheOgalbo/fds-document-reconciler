"""Simple on-disk cache for expensive query/comparison/summary results."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "query_cache"
CACHE_SCHEMA_VERSION = 2


def _cache_key(query: str, document_ids: list[str]) -> str:
    payload = json.dumps(
        {
            "v": CACHE_SCHEMA_VERSION,
            "query": query.strip().lower(),
            "document_ids": sorted(document_ids),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def get_cached(query: str, document_ids: list[str]) -> dict[str, Any] | None:
    path = _CACHE_DIR / f"{_cache_key(query, document_ids)}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def set_cached(query: str, document_ids: list[str], payload: dict[str, Any]) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _CACHE_DIR / f"{_cache_key(query, document_ids)}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
