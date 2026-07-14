"""Query/comparison/summary response cache.

Prefers Redis when REDIS_URL is reachable; falls back to on-disk JSON so
local unit tests and Redis outages still work without changing callers.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "query_cache"
CACHE_SCHEMA_VERSION = 3

_redis_client = None
_redis_failed = False


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


def _redis_key(query: str, document_ids: list[str]) -> str:
    return f"rag_query:{_cache_key(query, document_ids)}"


def _get_redis():
    """Lazy Redis client. Returns None when Redis is unset or unreachable."""
    global _redis_client, _redis_failed
    if _redis_failed:
        return None
    if _redis_client is not None:
        return _redis_client

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.redis_url:
        _redis_failed = True
        return None

    try:
        import redis

        client = redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1.5)
        client.ping()
        _redis_client = client
        logger.info("Query cache connected to Redis at %s", settings.redis_url)
        return _redis_client
    except Exception as exc:
        _redis_failed = True
        logger.warning("Redis unavailable (%s); using on-disk query cache", exc)
        return None


def reset_redis_state_for_tests() -> None:
    """Test helper: clear cached Redis client / failure flag."""
    global _redis_client, _redis_failed
    _redis_client = None
    _redis_failed = False


def get_cached(query: str, document_ids: list[str]) -> dict[str, Any] | None:
    key = _cache_key(query, document_ids)
    client = _get_redis()
    if client is not None:
        try:
            cached = client.get(_redis_key(query, document_ids))
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.warning("Redis get failed: %s", exc)

    path = _CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def set_cached(query: str, document_ids: list[str], payload: dict[str, Any]) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    serialized = json.dumps(payload, ensure_ascii=False)

    client = _get_redis()
    if client is not None:
        try:
            client.setex(
                _redis_key(query, document_ids),
                settings.query_cache_ttl_seconds,
                serialized,
            )
        except Exception as exc:
            logger.warning("Redis set failed: %s", exc)

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _CACHE_DIR / f"{_cache_key(query, document_ids)}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def is_redis_available() -> bool:
    return _get_redis() is not None
