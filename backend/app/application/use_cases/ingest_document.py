"""
Application use case: IngestDocument.

Orchestrates the full ingestion pipeline: parse -> hierarchical chunk ->
embed child slices -> upsert to Pinecone. PARENT chunks are stored with a
zero vector (retrieval searches children only; parents are fetched by ID).
"""
from __future__ import annotations

import uuid
from pathlib import Path

from app.application.dto.schemas import IngestResponse
from app.core.config import get_settings, require_ai_services
from app.domain.entities.document import ChunkType
from app.domain.exceptions.errors import DomainError, EmbeddingRateLimitError
from app.infrastructure.ai.local_embedder import hash_embed_batch
from app.infrastructure.ai.llm_gateway import get_llm_gateway
from app.infrastructure.parsing.chunker import build_parent_child_chunks
from app.infrastructure.parsing.parsers import parse_document
from app.infrastructure.parsing.table_chunking import count_markdown_table_stats
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
    page_text = "\n\n".join(p.text or "" for p in pages)
    tables_parsed, table_rows_parsed = count_markdown_table_stats(page_text)
    chunks = build_parent_child_chunks(
        pages=pages, document_id=document_id, document_name=document_name, version=version
    )

    child_chunks = [c for c in chunks if c.chunk_type == ChunkType.CHILD]
    parent_chunks = [c for c in chunks if c.chunk_type == ChunkType.PARENT]

    if not child_chunks:
        raise DomainError("No child chunks were created — the document may be empty or unreadable.")

    embed_warning: str | None = None
    embeddings = await _embed_child_chunks(child_chunks)
    if embeddings is None:
        embed_warning = (
            "Cloud embeddings were rate-limited — indexed with local fallback vectors. "
            "Semantic search quality may be reduced until you re-ingest after a few minutes."
        )
        embeddings = hash_embed_batch([c.content for c in child_chunks])

    if len(embeddings) != len(child_chunks):
        raise DomainError(
            f"Embedding provider returned {len(embeddings)} vectors for {len(child_chunks)} chunks."
        )
    for chunk, embedding in zip(child_chunks, embeddings):
        chunk.embedding = embedding

    zero_vector = [0.0] * len(child_chunks[0].embedding or [])
    if not zero_vector:
        raise DomainError("Embedding provider returned empty vectors.")
    for parent in parent_chunks:
        parent.embedding = zero_vector

    _store.upsert_chunks(chunks)

    parent_count = sum(1 for c in chunks if c.chunk_type == ChunkType.PARENT)
    child_count = sum(1 for c in chunks if c.chunk_type == ChunkType.CHILD)

    warning = _ingest_warning(
        file_path=file_path,
        pages=len(pages),
        parent_count=parent_count,
        child_count=child_count,
        total_chars=sum(len(p.text or "") for p in pages),
    )
    if embed_warning:
        warning = f"{embed_warning} {warning}".strip() if warning else embed_warning

    return IngestResponse(
        document_id=document_id,
        document_name=document_name,
        version=version,
        chunks_created=len(chunks),
        parent_chunks=parent_count,
        child_chunks=child_count,
        pages_parsed=len(pages),
        tables_parsed=tables_parsed,
        table_rows_parsed=table_rows_parsed,
        ingest_warning=warning,
    )


def _ingest_warning(
    *,
    file_path: str,
    pages: int,
    parent_count: int,
    child_count: int,
    total_chars: int,
) -> str | None:
    file_size_kb = Path(file_path).stat().st_size / 1024

    if parent_count == 0:
        return "No indexable sections were created. The file may be empty or unreadable."

    if child_count == 0:
        return "No child chunks were created — search quality will be poor. Try re-uploading or use DOCX."

    if parent_count == 1 and pages >= 2 and total_chars > 2000:
        return (
            "Only one section was detected across multiple pages. "
            "Headings may not have been recognized — content was split by page as a fallback."
        )

    if file_size_kb > 100 and parent_count <= 1 and child_count < 4:
        return (
            "Very few chunks were created for this file size. "
            "The document structure may not have been detected correctly."
        )

    return None


def _using_mock_pinecone() -> bool:
    settings = get_settings()
    return settings.pinecone_api_key in {"", "mock_pinecone_key", "your-pinecone-key-here"}


async def _embed_child_chunks(child_chunks: list) -> list[list[float]] | None:
    """
    Embed all child chunks via the cloud provider.
    Returns None when rate-limited and mock Pinecone allows local fallback.
    """
    batch_size = 100
    all_embeddings: list[list[float]] = []
    # Fewer retries during ingest — mock Pinecone can fall back to local vectors quickly.
    max_attempts = 3 if _using_mock_pinecone() else None
    try:
        for i in range(0, len(child_chunks), batch_size):
            batch = child_chunks[i : i + batch_size]
            batch_embeddings = await _get_llm().embed(
                [c.content for c in batch],
                max_attempts=max_attempts,
            )
            all_embeddings.extend(batch_embeddings)
        return all_embeddings
    except EmbeddingRateLimitError:
        if _using_mock_pinecone():
            return None
        raise
