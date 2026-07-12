"""
Shared token-counting utility.

Context-window budgeting (MAX_CONTEXT_TOKENS) and chunk-size decisions
(CHUNK_SIZE_TOKENS, PARENT_CHUNK_SIZE_TOKENS) both depend on knowing how
many tokens a piece of text actually costs. A `len(text) // 4` heuristic
is a common rule of thumb but can drift meaningfully from the real count
depending on content (numbers, punctuation, technical jargon all tokenize
differently from prose) — and this system's own token budget is exactly
the kind of place where under-counting could silently push a prompt over
the model's real context window.

This module uses `tiktoken` (OpenAI's actual tokenizer) for an accurate
count, but falls back gracefully to the char/4 approximation if the
encoding can't be loaded — `tiktoken` fetches its vocabulary file from a
remote URL the first time a given encoding is used, so a environment
without egress to that host (a locked-down container, an air-gapped
deployment, or an offline test sandbox) would otherwise crash. Token
counting degrading to an approximation is an acceptable fallback; crashing
document ingestion because a vocab file couldn't be downloaded is not.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_encoder = None
_encoder_load_attempted = False
_encoder_load_failed = False


def _get_encoder():
    global _encoder, _encoder_load_attempted, _encoder_load_failed
    if _encoder_load_attempted:
        return _encoder
    _encoder_load_attempted = True
    try:
        import tiktoken

        _encoder = tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        _encoder_load_failed = True
        logger.warning(
            "tiktoken encoding unavailable (%s) — falling back to a char/4 "
            "token approximation. This is expected in network-restricted "
            "environments; it does not affect correctness, only precision "
            "of context-window budgeting.",
            e,
        )
        _encoder = None
    return _encoder


def count_tokens(text: str) -> int:
    """Returns an exact tiktoken count when available, otherwise a
    char/4 approximation. Never raises — token counting must never be the
    reason ingestion or retrieval fails."""
    if not text:
        return 0
    encoder = _get_encoder()
    if encoder is not None:
        try:
            return len(encoder.encode(text))
        except Exception:
            pass  # fall through to approximation below
    return max(1, len(text) // 4)


def truncate_to_token_budget(text: str, budget: int) -> str:
    """
    Trims `text` down to at most `budget` tokens. Uses the real tokenizer
    (encode -> slice tokens -> decode) when available for an exact cut;
    falls back to a char-based cut (budget * 4 chars) otherwise. Either
    way, this is the function that actually enforces MAX_CONTEXT_TOKENS —
    the setting that keeps a request from silently exceeding the model's
    real context window.
    """
    if not text:
        return text

    encoder = _get_encoder()
    if encoder is not None:
        try:
            tokens = encoder.encode(text)
            if len(tokens) <= budget:
                return text
            truncated = encoder.decode(tokens[:budget])
            return truncated + "\n\n[...context truncated to fit token budget...]"
        except Exception:
            pass  # fall through to approximation below

    approx_tokens = len(text) // 4
    if approx_tokens <= budget:
        return text
    max_chars = budget * 4
    return text[:max_chars] + "\n\n[...context truncated to fit token budget...]"


def using_exact_counting() -> bool:
    """Exposed for observability/health checks — lets callers report
    whether token budgeting is using real counts or the approximation."""
    _get_encoder()
    return not _encoder_load_failed
