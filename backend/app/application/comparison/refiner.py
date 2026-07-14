"""Post-processing helpers to improve MATCH / DIFF / MISSING accuracy."""
from __future__ import annotations

from app.domain.entities.document import ComparisonReport, DiffItem, MatchItem, MissingItem


def should_supplement_llm_report(report: ComparisonReport, retrieved_chunks: list[dict]) -> bool:
    """Detect when LLM output is likely incomplete (e.g. zero matches with balanced retrieval)."""
    if not retrieved_chunks:
        return False

    by_doc: dict[str, int] = {}
    for hit in retrieved_chunks:
        meta = hit.get("metadata", {}) or {}
        doc_key = str(meta.get("document_id") or meta.get("document") or "")
        if doc_key:
            by_doc[doc_key] = by_doc.get(doc_key, 0) + 1

    if len(by_doc) < 2:
        return False

    total = len(report.diff) + len(report.match) + len(report.missing)
    if total == 0:
        return True

    min_per_doc = min(by_doc.values())
    if len(report.match) == 0 and min_per_doc >= 2:
        return True

    # Heavily skewed toward missing with little evidence of real one-sided content.
    if len(report.missing) >= 2 and len(report.match) == 0 and len(report.diff) <= 1:
        return True

    return False


def reclassify_high_similarity_diffs(
    report: ComparisonReport,
    *,
    match_threshold: float = 0.82,
) -> ComparisonReport:
    """Move diff rows that are actually near-identical into match."""
    kept_diff: list[DiffItem] = []
    promoted: list[MatchItem] = list(report.match)

    for item in report.diff:
        sim = item.semantic_similarity
        if sim is not None and sim >= match_threshold:
            promoted.append(
                MatchItem(
                    textA=item.docA_text[:300],
                    textB=item.docB_text[:300],
                    source=f"{item.sourceA} + {item.sourceB}",
                    similarity_score=sim,
                )
            )
        else:
            kept_diff.append(item)

    return ComparisonReport(missing=report.missing, diff=kept_diff, match=promoted)


def _norm_text(text: str) -> str:
    return " ".join(text.lower().split())[:240]


def merge_comparison_reports(primary: ComparisonReport, supplement: ComparisonReport) -> ComparisonReport:
    """Union primary LLM report with semantic supplement, deduping by normalized text."""
    seen_match: set[str] = {_norm_text(f"{m.textA}|{m.textB}") for m in primary.match}
    seen_diff: set[str] = {_norm_text(f"{d.docA_text}|{d.docB_text}") for d in primary.diff}
    seen_missing: set[str] = {_norm_text(m.text) for m in primary.missing}

    match = list(primary.match)
    diff = list(primary.diff)
    missing = list(primary.missing)

    for item in supplement.match:
        key = _norm_text(f"{item.textA}|{item.textB}")
        if key not in seen_match:
            seen_match.add(key)
            match.append(item)

    for item in supplement.diff:
        key = _norm_text(f"{item.docA_text}|{item.docB_text}")
        if key not in seen_diff and key not in seen_match:
            seen_diff.add(key)
            diff.append(item)

    for item in supplement.missing:
        key = _norm_text(item.text)
        if key not in seen_missing:
            seen_missing.add(key)
            missing.append(item)

    return ComparisonReport(missing=missing, diff=diff, match=match)
