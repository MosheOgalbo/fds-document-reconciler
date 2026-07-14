"""
Deterministic local embeddings for demo / offline runs.

Used only when the cloud embedding provider is rate-limited and Pinecone is
running in mock mode. Not suitable for production semantic search quality.
"""
from __future__ import annotations

import hashlib
import struct


def hash_embed(text: str, dim: int = 3072) -> list[float]:
    """Map text to a unit-normalized vector of the requested dimension."""
    vec = [0.0] * dim
    seed = text.encode("utf-8")
    for i in range(dim):
        digest = hashlib.sha256(seed + struct.pack(">I", i)).digest()
        vec[i] = (int.from_bytes(digest[:4], "big") / 2**32) * 2 - 1
    norm = sum(x * x for x in vec) ** 0.5
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def hash_embed_batch(texts: list[str], dim: int = 3072) -> list[list[float]]:
    return [hash_embed(t, dim=dim) for t in texts]
