"""ComparisonAgent integration tests with fake LLM (no live API calls)."""
from __future__ import annotations

import pytest

from app.application.agents.comparison_agent import ComparisonAgent
from app.application.agents.state import GraphState


class _FakeLLM:
    def __init__(self, payload: dict | None = None, fail: bool = False):
        self.payload = payload
        self.fail = fail
        self.embed_calls = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls += 1
        # Same first sentence → high similarity; otherwise distinct.
        out = []
        for t in texts:
            if "Phase A delivers" in t and "live field validation" not in t:
                out.append([1.0, 0.0, 0.0])
            elif "Phase A delivers" in t:
                out.append([0.85, 0.4, 0.0])
            elif "Phase B" in t:
                out.append([0.0, 1.0, 0.0])
            elif "Phase C" in t:
                out.append([0.0, 0.0, 1.0])
            else:
                out.append([0.2, 0.2, 0.2])
        return out

    async def chat_json(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("LLM down")
        return self.payload


def _retrieved_identical() -> list[dict]:
    text = "Phase A delivers real-time QA on PB Draft with live field validation."
    text_b = "Phase B retains the current process structure."
    return [
        {
            "chunk_id": "a1",
            "metadata": {
                "document": "FDS_PriceBook_V0.pdf",
                "version": "v0",
                "section": "Phase A",
                "page": 4,
                "content": text,
            },
        },
        {
            "chunk_id": "a2",
            "metadata": {
                "document": "FDS_PriceBook_V0.pdf",
                "version": "v0",
                "section": "Phase B",
                "page": 5,
                "content": text_b,
            },
        },
        {
            "chunk_id": "b1",
            "metadata": {
                "document": "FDS_PriceBook_V5.docx",
                "version": "v5",
                "section": "Phase A",
                "page": 4,
                "content": text,
            },
        },
        {
            "chunk_id": "b2",
            "metadata": {
                "document": "FDS_PriceBook_V5.docx",
                "version": "v5",
                "section": "Phase B",
                "page": 5,
                "content": text_b,
            },
        },
    ]


@pytest.mark.asyncio
async def test_comparison_identical_documents_via_llm():
    llm = _FakeLLM(
        {
            "missing": [],
            "diff": [],
            "match": [
                {
                    "textA": "Phase A delivers real-time QA on PB Draft with live field validation.",
                    "textB": "Phase A delivers real-time QA on PB Draft with live field validation.",
                    "source": "FDS_PriceBook_V0.pdf / Page 4 + FDS_PriceBook_V5.docx / Page 4",
                }
            ],
        }
    )
    agent = ComparisonAgent(llm)
    state: GraphState = {
        "user_query": "Compare the two versions",
        "document_ids": ["doc_a", "doc_b"],
        "expanded_context": "identical content context",
        "retrieved_chunks": _retrieved_identical(),
        "agent_trace": [],
    }
    result = await agent.run(state)
    report = result["comparison_report"]
    assert len(report.match) > 0
    assert len(report.diff) == 0
    assert len(report.missing) == 0
    assert report.match[0].similarity_score is not None
    assert llm.embed_calls > 0
    assert any("similarity=enriched" in t for t in result["agent_trace"])


@pytest.mark.asyncio
async def test_comparison_falls_back_to_semantic_when_llm_fails():
    agent = ComparisonAgent(_FakeLLM(fail=True))
    state: GraphState = {
        "user_query": "Compare",
        "document_ids": ["doc_a", "doc_b"],
        "expanded_context": "",
        "retrieved_chunks": _retrieved_identical(),
        "agent_trace": [],
    }
    result = await agent.run(state)
    report = result["comparison_report"]
    assert report is not None
    assert any("fallback" in t for t in result["agent_trace"])
    # Identical paired texts should produce at least one match via embeddings.
    assert len(report.match) + len(report.diff) + len(report.missing) > 0


@pytest.mark.asyncio
async def test_comparison_empty_retrieval_is_safe():
    agent = ComparisonAgent(_FakeLLM(fail=True))
    state: GraphState = {
        "user_query": "Compare",
        "document_ids": ["doc_a", "doc_b"],
        "expanded_context": "",
        "retrieved_chunks": [],
        "agent_trace": [],
    }
    result = await agent.run(state)
    report = result["comparison_report"]
    assert report.missing == []
    assert report.diff == []
    assert report.match == []
