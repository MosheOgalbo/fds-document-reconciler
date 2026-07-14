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

MATCH_THRESHOLD = 0.78
DIFF_THRESHOLD = 0.38
MAX_ROWS_PER_CATEGORY = 24


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
    max_rows: int = MAX_ROWS_PER_CATEGORY,
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

    # Section-aware pairing first, then global best-pair greedy alignment.
    pairs = _section_pair_candidates(doc_a_chunks, doc_b_chunks, emb_a, emb_b)
    pairs.extend(_global_pair_candidates(doc_a_chunks, doc_b_chunks, emb_a, emb_b))
    pairs.sort(key=lambda p: p[4], reverse=True)

    match: list[MatchItem] = []
    diff: list[DiffItem] = []
    missing: list[MissingItem] = []
    used_a: set[int] = set()
    used_b: set[int] = set()

    for i, j, chunk_a, chunk_b, best_sim in pairs:
        if i in used_a or j in used_b:
            continue

        label = classify_similarity(best_sim, match_threshold=match_threshold, diff_threshold=diff_threshold)
        loc_a = _meta_location(chunk_a)
        loc_b = _meta_location(chunk_b)

        if label == "match":
            used_a.add(i)
            used_b.add(j)
            match.append(
                MatchItem(
                    textA=chunk_a["text"][:300],
                    textB=chunk_b["text"][:300],
                    source=f"{loc_a} + {loc_b}",
                    similarity_score=round(best_sim, 4),
                )
            )
        elif label == "diff":
            used_a.add(i)
            used_b.add(j)
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

    for i, chunk_a in enumerate(doc_a_chunks):
        if i not in used_a:
            missing.append(
                MissingItem(
                    text=chunk_a["text"][:500],
                    source_file=_meta_doc(chunk_a),
                    location=_meta_location(chunk_a),
                )
            )

    for j, chunk_b in enumerate(doc_b_chunks):
        if j not in used_b:
            missing.append(
                MissingItem(
                    text=chunk_b["text"][:500],
                    source_file=_meta_doc(chunk_b),
                    location=_meta_location(chunk_b),
                )
            )

    return ComparisonReport(
        missing=missing[:max_rows],
        diff=diff[:max_rows],
        match=match[:max_rows],
    )


def _section_key(chunk: dict) -> str:
    meta = _meta(chunk)
    section = str(meta.get("section") or meta.get("subsection_heading") or meta.get("heading") or "")
    return section.strip().lower()


def _section_pair_candidates(
    doc_a_chunks: list[dict],
    doc_b_chunks: list[dict],
    emb_a: list[list[float]],
    emb_b: list[list[float]],
) -> list[tuple[int, int, dict, dict, float]]:
    """Prefer comparing chunks that share the same section heading."""
    pairs: list[tuple[int, int, dict, dict, float]] = []
    b_by_section: dict[str, list[int]] = {}
    for j, chunk_b in enumerate(doc_b_chunks):
        key = _section_key(chunk_b)
        if key:
            b_by_section.setdefault(key, []).append(j)

    for i, chunk_a in enumerate(doc_a_chunks):
        key = _section_key(chunk_a)
        if not key:
            continue
        for j in b_by_section.get(key, []):
            sim = cosine_similarity(emb_a[i], emb_b[j])
            pairs.append((i, j, chunk_a, doc_b_chunks[j], sim))
    return pairs


def _global_pair_candidates(
    doc_a_chunks: list[dict],
    doc_b_chunks: list[dict],
    emb_a: list[list[float]],
    emb_b: list[list[float]],
) -> list[tuple[int, int, dict, dict, float]]:
    pairs: list[tuple[int, int, dict, dict, float]] = []
    for i, chunk_a in enumerate(doc_a_chunks):
        for j, emb_bj in enumerate(emb_b):
            sim = cosine_similarity(emb_a[i], emb_bj)
            pairs.append((i, j, chunk_a, doc_b_chunks[j], sim))
    return pairs


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
