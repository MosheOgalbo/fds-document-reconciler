"""
Application use case: IngestDocument.

Orchestrates the full ingestion pipeline: parse -> hierarchical chunk ->
embed -> upsert to Pinecone. This is where PARENT chunks get embedded too
(so fetch_parent metadata includes the vector's own content field) even
though only CHILD chunks are used for similarity search — parents are
fetched by ID, not searched, so their embedding is only needed to satisfy
Pinecone's schema, not for retrieval quality.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from app.application.dto.schemas import IngestResponse
from app.core.config import require_ai_services
from app.domain.entities.document import ChunkType
from app.infrastructure.ai.llm_gateway import get_llm_gateway
from app.infrastructure.parsing.chunker import build_parent_child_chunks
from app.infrastructure.parsing.parsers import parse_document
from app.infrastructure.vectordb.pinecone_client import PineconeVectorStore

_store = PineconeVectorStore()
_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm_gateway()
    return _llm


async def execute(file_path: str, document_name: str, version: str) -> IngestResponse:
    require_ai_services()
    document_id = str(uuid.uuid4())

    pages = parse_document(file_path)
    chunks = build_parent_child_chunks(
        pages=pages, document_id=document_id, document_name=document_name, version=version
    )

    # Batch-embed all chunk contents in one call per batch of 100 (API limit headroom).
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        embeddings = await _get_llm().embed([c.content for c in batch])
        for chunk, embedding in zip(batch, embeddings):
            chunk.embedding = embedding

    _store.upsert_chunks(chunks)

    parent_count = sum(1 for c in chunks if c.chunk_type == ChunkType.PARENT)
    child_count = sum(1 for c in chunks if c.chunk_type == ChunkType.CHILD)

    return IngestResponse(
        document_id=document_id,
        document_name=document_name,
        version=version,
        chunks_created=len(chunks),
        parent_chunks=parent_count,
        child_chunks=child_count,
    )
