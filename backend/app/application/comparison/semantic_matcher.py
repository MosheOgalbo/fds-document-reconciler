"""
Embedding-based MATCH / DIFF / MISSING detection and similarity enrichment.

Used to (1) improve the deterministic comparison fallback beyond Jaccard, and
(2) attach numeric similarity scores to LLM-produced comparison rows so the UI
can show how related two paired spans are.
"""
from __future__ import annotations

import math
from typing import Protocol

from app.domain.entities.document import ComparisonReport, DiffItem, MatchItem, MissingItem

MATCH_THRESHOLD = 0.80
DIFF_THRESHOLD = 0.40


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def classify_similarity(
    score: float,
    *,
    match_threshold: float = MATCH_THRESHOLD,
    diff_threshold: float = DIFF_THRESHOLD,
) -> str:
    if score >= match_threshold:
        return "match"
    if score >= diff_threshold:
        return "diff"
    return "missing"


async def detect_diffs_semantic(
    doc_a_chunks: list[dict],
    doc_b_chunks: list[dict],
    embedder: Embedder,
    *,
    match_threshold: float = MATCH_THRESHOLD,
    diff_threshold: float = DIFF_THRESHOLD,
) -> ComparisonReport:
    """
    Compare chunk texts via embedding cosine similarity.

    Each item in doc_*_chunks must have at least:
      {"text": str, "metadata": {"doc_name"|"document", "page", "section"|"subsection_heading"}}
    """
    if not doc_a_chunks:
        return ComparisonReport(
            missing=[
                MissingItem(
                    text=c["text"],
                    source_file=_meta_doc(c),
                    location=_meta_location(c),
                )
                for c in doc_b_chunks
            ]
        )
    if not doc_b_chunks:
        return ComparisonReport(
            missing=[
                MissingItem(
                    text=c["text"],
                    source_file=_meta_doc(c),
                    location=_meta_location(c),
                )
                for c in doc_a_chunks
            ]
        )

    texts_a = [c["text"] for c in doc_a_chunks]
    texts_b = [c["text"] for c in doc_b_chunks]
    emb_a = await embedder.embed(texts_a)
    emb_b = await embedder.embed(texts_b)

    match: list[MatchItem] = []
    diff: list[DiffItem] = []
    missing: list[MissingItem] = []
    matched_b: set[int] = set()

    for i, chunk_a in enumerate(doc_a_chunks):
        best_j = 0
        best_sim = -1.0
        for j, emb_bj in enumerate(emb_b):
            sim = cosine_similarity(emb_a[i], emb_bj)
            if sim > best_sim:
                best_sim, best_j = sim, j

        chunk_b = doc_b_chunks[best_j]
        label = classify_similarity(best_sim, match_threshold=match_threshold, diff_threshold=diff_threshold)
        loc_a = _meta_location(chunk_a)
        loc_b = _meta_location(chunk_b)

        if label == "match":
            matched_b.add(best_j)
            match.append(
                MatchItem(
                    textA=chunk_a["text"][:300],
                    textB=chunk_b["text"][:300],
                    source=f"{loc_a} + {loc_b}",
                    similarity_score=round(best_sim, 4),
                )
            )
        elif label == "diff":
            matched_b.add(best_j)
            diff.append(
                DiffItem(
                    docA_text=chunk_a["text"][:500],
                    docB_text=chunk_b["text"][:500],
                    reason=f"Semantically related but changed (similarity={best_sim:.2f}).",
                    sourceA=loc_a,
                    sourceB=loc_b,
                    semantic_similarity=round(best_sim, 4),
                )
            )
        else:
            missing.append(
                MissingItem(
                    text=chunk_a["text"][:500],
                    source_file=_meta_doc(chunk_a),
                    location=loc_a,
                )
            )

    for j, chunk_b in enumerate(doc_b_chunks):
        if j not in matched_b:
            missing.append(
                MissingItem(
                    text=chunk_b["text"][:500],
                    source_file=_meta_doc(chunk_b),
                    location=_meta_location(chunk_b),
                )
            )

    return ComparisonReport(missing=missing[:12], diff=diff[:12], match=match[:12])


async def enrich_report_similarities(report: ComparisonReport, embedder: Embedder) -> ComparisonReport:
    """Attach cosine similarity scores to existing LLM/heuristic comparison rows."""
    pair_texts: list[tuple[str, str]] = []
    for d in report.diff:
        pair_texts.append((d.docA_text, d.docB_text))
    for m in report.match:
        pair_texts.append((m.textA, m.textB))

    if not pair_texts:
        return report

    left = [a for a, _ in pair_texts]
    right = [b for _, b in pair_texts]
    emb_left = await embedder.embed(left)
    emb_right = await embedder.embed(right)

    idx = 0
    for d in report.diff:
        d.semantic_similarity = round(cosine_similarity(emb_left[idx], emb_right[idx]), 4)
        idx += 1
    for m in report.match:
        m.similarity_score = round(cosine_similarity(emb_left[idx], emb_right[idx]), 4)
        idx += 1
    return report


def _meta(chunk: dict) -> dict:
    return chunk.get("metadata") or {}


def _meta_doc(chunk: dict) -> str:
    meta = _meta(chunk)
    return str(meta.get("doc_name") or meta.get("document") or meta.get("filename") or "unknown")


def _meta_location(chunk: dict) -> str:
    meta = _meta(chunk)
    doc = _meta_doc(chunk)
    page = meta.get("page")
    section = meta.get("subsection_heading") or meta.get("section") or meta.get("heading") or ""
    parts = [doc]
    if page not in (None, "", 0):
        parts.append(f"Page {page}")
    if section:
        parts.append(str(section))
    return ", ".join(parts)
