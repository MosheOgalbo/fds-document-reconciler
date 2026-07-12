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

import logging
from typing import Optional

from app.core.config import get_settings
from app.domain.entities.document import DocumentChunk
from app.domain.exceptions.errors import RetrievalError

logger = logging.getLogger(__name__)


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
