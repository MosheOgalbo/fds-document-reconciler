"""Unit tests for comparison report refinement helpers."""
from __future__ import annotations

from app.application.comparison.refiner import (
    merge_comparison_reports,
    reclassify_high_similarity_diffs,
    should_supplement_llm_report,
)
from app.domain.entities.document import ComparisonReport, DiffItem, MatchItem, MissingItem


def test_should_supplement_when_no_matches_but_balanced_retrieval():
    report = ComparisonReport(
        missing=[MissingItem(text="only in A", source_file="a.pdf", location="p1")],
        diff=[DiffItem(docA_text="a", docB_text="b", reason="changed", sourceA="a", sourceB="b")],
        match=[],
    )
    retrieved = [
        {"metadata": {"document_id": "doc_a", "document": "A.pdf"}},
        {"metadata": {"document_id": "doc_a", "document": "A.pdf"}},
        {"metadata": {"document_id": "doc_b", "document": "B.docx"}},
        {"metadata": {"document_id": "doc_b", "document": "B.docx"}},
    ]
    assert should_supplement_llm_report(report, retrieved) is True


def test_reclassify_promotes_high_similarity_diff_to_match():
    report = ComparisonReport(
        diff=[
            DiffItem(
                docA_text="same meaning",
                docB_text="same meaning reworded",
                reason="minor",
                sourceA="a",
                sourceB="b",
                semantic_similarity=0.91,
            )
        ]
    )
    refined = reclassify_high_similarity_diffs(report)
    assert len(refined.match) == 1
    assert refined.diff == []


def test_merge_deduplicates_rows():
    primary = ComparisonReport(
        match=[MatchItem(textA="x", textB="x", source="s1")],
        diff=[],
        missing=[],
    )
    supplement = ComparisonReport(
        match=[MatchItem(textA="x", textB="x", source="s1"), MatchItem(textA="y", textB="y", source="s2")],
        diff=[],
        missing=[],
    )
    merged = merge_comparison_reports(primary, supplement)
    assert len(merged.match) == 2
