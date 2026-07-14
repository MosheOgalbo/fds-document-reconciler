import pytest

from app.domain.exceptions.errors import EmbeddingRateLimitError
from app.infrastructure.ai.embed_service import embed_with_fallback
from app.infrastructure.ai.local_embedder import hash_embed


class _FlakyEmbedder:
    async def embed(self, texts: list[str], max_attempts: int | None = None) -> list[list[float]]:
        raise EmbeddingRateLimitError("rate limited")


@pytest.mark.asyncio
async def test_embed_with_fallback_uses_local_vectors():
    vecs = await embed_with_fallback(_FlakyEmbedder(), ["hello", "world"])
    assert len(vecs) == 2
    assert vecs[0] == hash_embed("hello")
    assert vecs[1] == hash_embed("world")
