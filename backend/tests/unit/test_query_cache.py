"""Cache key + disk fallback tests (Redis optional)."""
from __future__ import annotations

from app.infrastructure.repositories import query_cache


def test_cache_key_generation_is_deterministic(tmp_path, monkeypatch):
    query_cache.reset_redis_state_for_tests()
    monkeypatch.setattr(query_cache, "_CACHE_DIR", tmp_path)
    monkeypatch.setenv("REDIS_URL", "")
    # Force settings reload pick empty redis if needed — use disk path only.
    key1 = query_cache._cache_key("Hello", ["b", "a"])
    key2 = query_cache._cache_key("hello", ["a", "b"])
    assert key1 == key2


def test_disk_cache_roundtrip(tmp_path, monkeypatch):
    query_cache.reset_redis_state_for_tests()
    monkeypatch.setattr(query_cache, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(query_cache, "_redis_failed", True)

    payload = {"answer": "cached", "intent": "single_doc_chat"}
    query_cache.set_cached("What changed?", ["doc-1"], payload)
    got = query_cache.get_cached("what changed?", ["doc-1"])
    assert got == payload


def test_cache_miss_returns_none(tmp_path, monkeypatch):
    query_cache.reset_redis_state_for_tests()
    monkeypatch.setattr(query_cache, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(query_cache, "_redis_failed", True)
    assert query_cache.get_cached("missing query", ["x"]) is None
