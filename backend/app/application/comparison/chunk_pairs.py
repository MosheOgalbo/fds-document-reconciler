"""Build per-document chunk lists for comparison fallbacks."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.infrastructure.vectordb.pinecone_client import PineconeVectorStore


def build_doc_pair_chunk_lists(
    retrieved_chunks: list[dict],
    document_ids: list[str],
    store: Optional["PineconeVectorStore"] = None,
) -> tuple[list[dict], list[dict]]:
    """
    Group retrieved hits into Document A / Document B lists using document_ids order.
    Prefer parent chunk text when available for richer alignment.
    """
    by_key: dict[str, list[dict]] = {}

    for hit in retrieved_chunks:
        meta = hit.get("metadata", {}) or {}
        doc_id = str(meta.get("document_id") or "")
        doc_name = str(meta.get("document") or "")
        key = doc_id or doc_name
        if not key:
            continue

        content = str(meta.get("content") or "")
        parent_id = meta.get("parent_chunk_id")
        if store and parent_id:
            parent_meta = store.fetch_parent(str(parent_id))
            if parent_meta:
                content = str(parent_meta.get("content") or content)

        if not content.strip():
            continue

        section = str(meta.get("section") or meta.get("subsection_heading") or meta.get("heading") or "")
        entry = {
            "text": content,
            "metadata": {
                "document": doc_name or doc_id,
                "document_id": doc_id,
                "page": meta.get("page", 0),
                "section": section,
                "subsection_heading": section,
            },
        }

        # Dedupe by section within each document to avoid repeating the same parent block.
        bucket = by_key.setdefault(key, [])
        if section and any(e["metadata"].get("section") == section for e in bucket):
            continue
        bucket.append(entry)

    if len(document_ids) >= 2:
        a_key, b_key = document_ids[0], document_ids[1]
        chunks_a = _resolve_bucket(by_key, a_key)
        chunks_b = _resolve_bucket(by_key, b_key)
        if chunks_a and chunks_b:
            return chunks_a, chunks_b

    keys = list(by_key.keys())
    if len(keys) >= 2:
        return by_key[keys[0]], by_key[keys[1]]
    if len(keys) == 1:
        return by_key[keys[0]], []
    return [], []


def _resolve_bucket(by_key: dict[str, list[dict]], key: str) -> list[dict]:
    if key in by_key:
        return by_key[key]
    for bucket_key, items in by_key.items():
        if bucket_key == key:
            return items
        if items and items[0]["metadata"].get("document_id") == key:
            return items
        if items and items[0]["metadata"].get("document") == key:
            return items
    return []
