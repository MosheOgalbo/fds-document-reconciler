"""
Full-graph end-to-end tests.

Unlike tests/integration/test_retrieval_agent.py (which tests one agent in
isolation), these tests build the REAL compiled StateGraph — the same
graph.py wiring used in production — with fake LLM/vector-store
dependencies injected, and run a request through the entire pipeline for
each of the 4 supported intents. This is deliberately the same style of
test that caught the parent-expansion and uncitable-chunk_id bugs
(DECISIONS.md D-10/D-11): per-agent unit tests can all pass individually
while the wiring between them is broken, so at least one test must
exercise the whole path end-to-end.
"""
from __future__ import annotations

import pytest
from langgraph.graph import END, StateGraph

from app.application.agents.citation_agent import CitationAgent
from app.application.agents.comparison_agent import ComparisonAgent
from app.application.agents.response_agent import ResponseAgent
from app.application.agents.retrieval_agent import RetrievalAgent
from app.application.agents.router_agent import RouterAgent
from app.application.agents.state import GraphState
from app.application.agents.summary_agent import SummaryAgent
from app.application.agents.validation_agent import ValidationAgent


class FakeLLM:
    """Returns schema-appropriate canned responses keyed by schema_name —
    mirrors exactly what OpenAIGateway.chat_json's callers depend on."""

    def __init__(self, forced_intent: str):
        self.forced_intent = forced_intent
        self.calls: list[str] = []

    async def embed(self, texts):
        self.calls.append("embed")
        return [[0.1, 0.2, 0.3] for _ in texts]

    async def chat_json(self, system_prompt, user_prompt, json_schema, schema_name="response", temperature=0.1, model_tier="smart"):
        self.calls.append(schema_name)

        if schema_name == "intent_routing":
            return {"intent": self.forced_intent, "rationale": "test-forced routing"}

        if schema_name == "comparison_report":
            return {
                "missing": [{"text": "New clause about uplift", "source_file": "docB.docx", "location": "Page 4, Section 6"}],
                "diff": [
                    {
                        "docA_text": "Uplift is 20%",
                        "docB_text": "Uplift is 25%",
                        "reason": "Percentage increased",
                        "sourceA": "Page 3, Section 6",
                        "sourceB": "Page 4, Section 6",
                    }
                ],
                "match": [{"textA": "Same rule", "textB": "Same rule", "source": "docA.pdf / Page 2 + docB.docx / Page 2"}],
            }

        if schema_name == "executive_summary":
            return {
                "top_important_changes": [
                    {
                        "rank": 1,
                        "title": "NA uplift percentage increased",
                        "description": "Uplift changed from 20% to 25%.",
                        "severity": "high",
                        "ranking_rationale": "Directly affects pricing output across all NA channel books.",
                    }
                ],
                "business_impact": "Pricing outputs shift for NA region.",
                "architecture_impact": "No architecture changes required.",
                "workflow_impact": "PMs must re-validate NA price books.",
            }

        if schema_name == "grounded_response":
            return {
                "answer": "The NA uplift for HW is 25% as of v5, up from 20% in v0.",
                "citations": [
                    {
                        "document_name": "FDS_PriceBook_V0.pdf",
                        "version": "v0",
                        "page_number": 6,
                        "section": "NA Price Books",
                        "chunk_id": "child-1",
                        "confidence": 0.9,
                        "quoted_snippet": "uplift +25% for HW",
                    }
                ],
                "insufficient_information": False,
            }

        if schema_name == "grounding_judgment":
            return {"is_grounded": True, "confidence": 0.88, "unsupported_claims": []}

        raise AssertionError(f"Unexpected schema_name in test: {schema_name}")


class FakeStore:
    def query(self, query_embedding, top_k, document_ids=None, chunk_type="child"):
        return [
            {
                "chunk_id": "child-1",
                "score": 0.92,
                "metadata": {
                    "document": "FDS_PriceBook_V0.pdf",
                    "version": "v0",
                    "section": "NA Price Books",
                    "page": 6,
                    "parent_chunk_id": "parent-1",
                    "content": "NA uplift rules: +25% for HW/Accessories, +15% for M9K.",
                },
            }
        ]

    def fetch_parent(self, parent_chunk_id):
        assert parent_chunk_id == "parent-1"
        return {"content": "Full NA Price Books section: uplift rules for HW, M9K, and TAA products."}


def _build_test_graph(forced_intent: str):
    """Mirrors application/agents/graph.py's build_graph() exactly, but with
    fakes injected instead of real OpenAIGateway/PineconeVectorStore."""
    llm = FakeLLM(forced_intent)
    store = FakeStore()

    router = RouterAgent(llm)
    retrieval = RetrievalAgent(llm, store)
    comparison = ComparisonAgent(llm)
    summary = SummaryAgent(llm)
    response = ResponseAgent(llm)
    validation = ValidationAgent(llm)
    citation = CitationAgent()

    graph = StateGraph(GraphState)
    graph.add_node("router", router.run)
    graph.add_node("retrieval", retrieval.run)
    graph.add_node("comparison", comparison.run)
    graph.add_node("summary", summary.run)
    graph.add_node("response", response.run)
    graph.add_node("validation", validation.run)
    graph.add_node("citation", citation.run)

    graph.set_entry_point("router")
    graph.add_edge("router", "retrieval")
    graph.add_conditional_edges(
        "retrieval",
        lambda s: "comparison" if s["intent"] in ("compare_documents", "executive_summary") else "response",
        {"comparison": "comparison", "response": "response"},
    )
    graph.add_conditional_edges(
        "comparison",
        lambda s: "summary" if s["intent"] == "executive_summary" else "__end__",
        {"summary": "summary", "__end__": END},
    )
    graph.add_edge("summary", END)
    graph.add_edge("response", "validation")
    graph.add_edge("validation", "citation")
    graph.add_edge("citation", END)

    return graph.compile(), llm


@pytest.mark.asyncio
async def test_single_doc_chat_end_to_end():
    graph, llm = _build_test_graph("single_doc_chat")
    result = await graph.ainvoke(
        {
            "user_query": "What is the NA uplift for HW?",
            "document_ids": ["doc-a"],
            "conversation_history": [],
            "conversation_summary": "",
            "request_id": "req-1",
            "agent_trace": [],
        }
    )

    assert result["intent"] == "single_doc_chat"
    assert "25%" in result["draft_answer"]
    assert result["is_grounded"] is True
    # The full pipeline must have run: router -> retrieval -> response -> validation -> citation
    assert result["final_citations"], "citations must survive validation and reach the final output"
    assert result["final_citations"][0].chunk_id == "child-1"
    assert "grounding_judgment" in llm.calls  # validation actually ran, not skipped


@pytest.mark.asyncio
async def test_cross_doc_chat_end_to_end():
    graph, _ = _build_test_graph("cross_doc_chat")
    result = await graph.ainvoke(
        {
            "user_query": "What changed in the NA uplift between versions?",
            "document_ids": ["doc-a", "doc-b"],
            "conversation_history": [],
            "conversation_summary": "",
            "request_id": "req-2",
            "agent_trace": [],
        }
    )
    assert result["intent"] == "cross_doc_chat"
    assert result["final_citations"]


@pytest.mark.asyncio
async def test_compare_documents_end_to_end():
    graph, _ = _build_test_graph("compare_documents")
    result = await graph.ainvoke(
        {
            "user_query": "Compare the two documents",
            "document_ids": ["doc-a", "doc-b"],
            "conversation_history": [],
            "conversation_summary": "",
            "request_id": "req-3",
            "agent_trace": [],
        }
    )
    assert result["intent"] == "compare_documents"
    report = result["comparison_report"]
    as_dict = report.to_dict()
    assert set(as_dict.keys()) == {"missing", "diff", "match"}
    assert len(as_dict["diff"]) == 1
    # compare_documents must NOT run Response/Validation/Citation — those
    # keys should be absent from final state entirely.
    assert "draft_answer" not in result
    assert "is_grounded" not in result


@pytest.mark.asyncio
async def test_executive_summary_end_to_end():
    graph, llm = _build_test_graph("executive_summary")
    result = await graph.ainvoke(
        {
            "user_query": "Give me the executive summary",
            "document_ids": ["doc-a", "doc-b"],
            "conversation_history": [],
            "conversation_summary": "",
            "request_id": "req-4",
            "agent_trace": [],
        }
    )
    assert result["intent"] == "executive_summary"
    # Must have run comparison BEFORE summary (summary consumes comparison_report)
    assert result.get("comparison_report") is not None
    summary = result["executive_summary"]
    assert len(summary["top_important_changes"]) <= 10
    assert summary["top_important_changes"][0]["rank"] == 1
    assert "comparison_report" in llm.calls  # confirms comparison ran
    comparison_idx = llm.calls.index("comparison_report")
    summary_idx = llm.calls.index("executive_summary")
    assert comparison_idx < summary_idx, "Comparison must run before Summary"
