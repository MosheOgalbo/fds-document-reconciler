"""
Pinecone wrapper. Single index shared across all documents/versions,
disambiguated entirely via metadata filters (document, version) — chosen
over one-index-per-document because (a) cross-document chat needs to query
across documents in one call, (b) Pinecone serverless indexes have
per-index overhead that doesn't justify fragmenting by document.

Hybrid retrieval = dense vector similarity (semantic) combined with a
keyword/metadata pre-filter, rather than "true" sparse+dense hybrid (which
would need a sparse encoder like BM25/SPLADE running server-side). For a
take-home scope this dense+keyword-boost approach is the right tradeoff:
it captures exact identifiers (e.g. "REQ-114", price codes) that pure
embeddings sometimes blur, without standing up a second index type.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.domain.entities.document import DocumentChunk
from app.domain.exceptions.errors import RetrievalError

logger = logging.getLogger(__name__)

_MOCK_KEYS = {"your-pinecone-key-here", "", "mock_pinecone_key"}
_MOCK_INDEX_PATH = Path(__file__).resolve().parents[3] / "data" / "mock_vectors.json"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class _InMemoryIndex:
    """Lightweight Pinecone stand-in for local/interview runs without a cloud index."""

    def __init__(self):
        self._vectors: dict[str, dict] = {}
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not _MOCK_INDEX_PATH.exists():
            return
        try:
            self._vectors = json.loads(_MOCK_INDEX_PATH.read_text(encoding="utf-8"))
            logger.info("Loaded %d vectors from mock index disk cache", len(self._vectors))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load mock index from disk: %s", e)

    def _persist(self) -> None:
        _MOCK_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        _MOCK_INDEX_PATH.write_text(json.dumps(self._vectors), encoding="utf-8")

    def upsert(self, vectors: list[dict], namespace: str = "default") -> dict:
        for vec in vectors:
            self._vectors[vec["id"]] = vec
        self._persist()
        return {"upserted_count": len(vectors)}

    def query(
        self,
        vector: list[float],
        top_k: int,
        include_metadata: bool = True,
        filter: dict | None = None,
        namespace: str = "default",
    ) -> dict:
        matches = []
        for vec_id, vec in self._vectors.items():
            metadata = vec.get("metadata", {})
            if filter and not self._matches_filter(metadata, filter):
                continue
            score = _cosine_similarity(vector, vec.get("values", []))
            matches.append({"id": vec_id, "score": score, "metadata": metadata})
        matches.sort(key=lambda m: m["score"], reverse=True)
        return {"matches": matches[:top_k]}

    def lexical_query(self, query: str, top_k: int, filter: dict | None = None) -> dict:
        q_terms = {t for t in re.split(r"\\W+", query.lower()) if t and len(t) > 2}
        matches = []
        for vec_id, vec in self._vectors.items():
            metadata = vec.get("metadata", {})
            if filter and not self._matches_filter(metadata, filter):
                continue
            content = (metadata.get("content") or "").lower()
            c_terms = {t for t in re.split(r"\\W+", content) if t and len(t) > 2}
            overlap = len(q_terms & c_terms) / max(len(q_terms), 1)
            matches.append({"id": vec_id, "score": overlap, "metadata": metadata})
        matches.sort(key=lambda m: m["score"], reverse=True)
        return {"matches": matches[:top_k]}

    def list_document_ids(self) -> list[str]:
        ids: set[str] = set()
        for vec in self._vectors.values():
            doc_id = vec.get("metadata", {}).get("document_id")
            if doc_id:
                ids.add(doc_id)
        return sorted(ids)

    def fetch(self, ids: list[str], namespace: str = "default") -> dict:
        return {"vectors": {vec_id: self._vectors[vec_id] for vec_id in ids if vec_id in self._vectors}}

    @staticmethod
    def _matches_filter(metadata: dict, flt: dict) -> bool:
        for key, condition in flt.items():
            value = metadata.get(key)
            if isinstance(condition, dict):
                if "$in" in condition and value not in condition["$in"]:
                    return False
                if "$eq" in condition and value != condition["$eq"]:
                    return False
            elif value != condition:
                return False
        return True


_MOCK_INDEX: _InMemoryIndex | None = None


def _get_mock_index() -> _InMemoryIndex:
    global _MOCK_INDEX
    if _MOCK_INDEX is None:
        _MOCK_INDEX = _InMemoryIndex()
    return _MOCK_INDEX


class PineconeVectorStore:
    def __init__(self):
        settings = get_settings()
        self._settings = settings
        self._index = None  # lazy-initialized so tests can run w/o real API key

    def _get_index(self):
        if self._index is not None:
            return self._index
        try:
            from pinecone import Pinecone, ServerlessSpec
        except ImportError as e:
            raise RetrievalError("pinecone package not installed") from e

        # In-memory index for interview/demo runs without a Pinecone account.
        if self._settings.pinecone_api_key in _MOCK_KEYS:
            logger.warning("Pinecone API key is not configured. Using in-memory mock index.")
            self._index = _get_mock_index()
            return self._index

        pc = Pinecone(api_key=self._settings.pinecone_api_key)
        existing = [i["name"] for i in pc.list_indexes()]
        if self._settings.pinecone_index not in existing:
            pc.create_index(
                name=self._settings.pinecone_index,
                dimension=3072,  # text-embedding-3-large
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=self._settings.pinecone_cloud,
                    region=self._settings.pinecone_region,
                ),
            )
        self._index = pc.Index(self._settings.pinecone_index)
        return self._index

    def upsert_chunks(self, chunks: list[DocumentChunk], namespace: str = "default") -> int:
        if not chunks:
            return 0
        index = self._get_index()
        vectors = []
        for c in chunks:
            if c.embedding is None:
                raise RetrievalError(f"Chunk {c.chunk_id} has no embedding; run embedder before upsert")
            vectors.append(
                {
                    "id": c.chunk_id,
                    "values": c.embedding,
                    # Pinecone's real limit is ~40KB of metadata per vector.
                    # The previous 4000-char cap was arbitrary and would
                    # silently truncate PARENT chunks (~1600 tokens / ~6400+
                    # chars) below their intended size — exactly the content
                    # the retrieval agent's parent-expansion step depends on.
                    # 30000 chars leaves ample headroom under the real limit
                    # for the other metadata fields.
                    "metadata": {**c.to_metadata(), "content": c.content[:30000]},
                }
            )
        batch_size = 100
        total = 0
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]
            index.upsert(vectors=batch, namespace=namespace)
            total += len(batch)
        logger.info("Upserted %d vectors to Pinecone namespace=%s", total, namespace)
        return total

    def query(
        self,
        query_embedding: list[float],
        top_k: int,
        document_ids: Optional[list[str]] = None,
        chunk_type: Optional[str] = "child",
        namespace: str = "default",
    ) -> list[dict]:
        index = self._get_index()
        flt: dict = {}
        if document_ids:
            flt["document_id"] = {"$in": document_ids}
        if chunk_type:
            flt["chunk_type"] = {"$eq": chunk_type}

        try:
            result = index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                filter=flt or None,
                namespace=namespace,
            )
        except Exception as e:
            raise RetrievalError(f"Pinecone query failed: {e}") from e

        return [
            {
                "chunk_id": match["id"],
                "score": match["score"],
                "metadata": match.get("metadata", {}),
            }
            for match in result.get("matches", [])
        ]

    def fetch_parent(self, parent_chunk_id: str, namespace: str = "default") -> Optional[dict]:
        index = self._get_index()
        result = index.fetch(ids=[parent_chunk_id], namespace=namespace)
        vectors = result.get("vectors", {})
        vec = vectors.get(parent_chunk_id)
        return vec.get("metadata") if vec else None

    def lexical_query(
        self,
        query: str,
        top_k: int,
        document_ids: Optional[list[str]] = None,
        chunk_type: Optional[str] = "child",
        namespace: str = "default",
    ) -> list[dict]:
        index = self._get_index()
        flt: dict = {}
        if document_ids:
            flt["document_id"] = {"$in": document_ids}
        if chunk_type:
            flt["chunk_type"] = {"$eq": chunk_type}

        if hasattr(index, "lexical_query"):
            result = index.lexical_query(query=query, top_k=top_k, filter=flt or None)
            return [
                {"chunk_id": match["id"], "score": match["score"], "metadata": match.get("metadata", {})}
                for match in result.get("matches", [])
            ]
        # If using real Pinecone, lexical fallback isn't available.
        return []
