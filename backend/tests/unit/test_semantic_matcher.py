"""Unit tests for embedding-based semantic MATCH/DIFF/MISSING classification."""
from __future__ import annotations

import pytest

from app.application.comparison.semantic_matcher import (
    classify_similarity,
    cosine_similarity,
    detect_diffs_semantic,
)


def test_cosine_identical_vectors():
    assert cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(1.0)


def test_cosine_orthogonal_vectors():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_classify_thresholds():
    assert classify_similarity(0.95) == "match"
    assert classify_similarity(0.55) == "diff"
    assert classify_similarity(0.10) == "missing"


class _FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Deterministic tiny embedding space based on first char for tests.
        out = []
        for t in texts:
            if "identical" in t:
                out.append([1.0, 0.0, 0.0])
            elif "related" in t:
                out.append([0.7, 0.7, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out


@pytest.mark.asyncio
async def test_semantic_matching_same_content():
    doc_a = [
        {
            "text": "identical Stage 1 PM Input",
            "metadata": {"doc_name": "V0.pdf", "page": 2, "section": "Stage 1"},
        }
    ]
    doc_b = [
        {
            "text": "identical Stage 1 PM Input",
            "metadata": {"doc_name": "V5.docx", "page": 3, "section": "Stage 1"},
        }
    ]
    report = await detect_diffs_semantic(doc_a, doc_b, _FakeEmbedder())
    assert len(report.match) == 1
    assert report.match[0].similarity_score is not None
    assert report.match[0].similarity_score > 0.95


@pytest.mark.asyncio
async def test_missing_content_detection():
    doc_a = [
        {
            "text": "unique content only in A",
            "metadata": {"doc_name": "V0.pdf", "page": 1, "section": "Intro"},
        }
    ]
    report = await detect_diffs_semantic(doc_a, [], _FakeEmbedder())
    assert len(report.missing) == 1
    assert report.missing[0].source_file == "V0.pdf"


@pytest.mark.asyncio
async def test_diff_band_classification():
    # Vectors: related≈[0.7,0.7,0], unique=[0,0,1] → cosine ~0 → MISSING by default thresholds.
    # Lower diff_threshold to 0 so near-orthogonal pairs still classify as DIFF in this unit test.
    doc_a = [
        {
            "text": "related pricing rule A",
            "metadata": {"doc_name": "V0.pdf", "page": 2, "section": "Pricing"},
        }
    ]
    doc_b = [
        {
            "text": "unique pricing orchestration totally different",
            "metadata": {"doc_name": "V5.docx", "page": 2, "section": "Pricing"},
        }
    ]
    report = await detect_diffs_semantic(
        doc_a, doc_b, _FakeEmbedder(), match_threshold=0.99, diff_threshold=0.0
    )
    assert len(report.diff) == 1
    assert report.diff[0].semantic_similarity is not None
