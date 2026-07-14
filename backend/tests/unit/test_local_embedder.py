from app.infrastructure.ai.local_embedder import hash_embed, hash_embed_batch


def test_hash_embed_dimension_and_normalized():
    vec = hash_embed("pricing rule CPN format", dim=3072)
    assert len(vec) == 3072
    norm = sum(x * x for x in vec) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_hash_embed_is_deterministic():
    a = hash_embed("same text")
    b = hash_embed("same text")
    assert a == b


def test_hash_embed_batch():
    texts = ["alpha", "beta", "gamma"]
    batch = hash_embed_batch(texts, dim=128)
    assert len(batch) == 3
    assert all(len(v) == 128 for v in batch)
