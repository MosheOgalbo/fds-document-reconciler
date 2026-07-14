"""
Resilient embedding helper — fast local fallback when Gemini is rate-limited.

Compare/retrieval must not block for minutes on 429 retries; mock/demo mode
uses deterministic hash vectors so the workflow can still complete.
"""
from __future__ import annotations

import logging

import httpx

from app.domain.exceptions.errors import EmbeddingRateLimitError
from app.infrastructure.ai.local_embedder import hash_embed_batch
from app.infrastructure.ai.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

_QUERY_MAX_ATTEMPTS = 2


async def embed_with_fallback(
    llm: LLMGateway,
    texts: list[str],
    *,
    max_attempts: int = _QUERY_MAX_ATTEMPTS,
) -> list[list[float]]:
    if not texts:
        return []
    try:
        return await llm.embed(texts, max_attempts=max_attempts)
    except TypeError:
        return await llm.embed(texts)
    except EmbeddingRateLimitError as exc:
        logger.warning("Embedding rate-limited; using local fallback (%d texts): %s", len(texts), exc)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            logger.warning("Embedding HTTP 429; using local fallback (%d texts)", len(texts))
        else:
            raise
    except RuntimeError as exc:
        if "embed" in str(exc).lower() or "429" in str(exc):
            logger.warning("Embedding runtime failure; using local fallback (%d texts): %s", len(texts), exc)
        else:
            raise
    return hash_embed_batch(texts)
