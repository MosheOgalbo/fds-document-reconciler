"""
LangGraph workflow assembly.

Flow:

    Router (fast model)
      |
      +-- intent=single_doc_chat / cross_doc_chat
      |     --> Retrieval --> Response (smart) --> Validation (smart) --> Citation --> END
      |
      +-- intent=compare_documents
      |     --> Retrieval --> Comparison (smart) --> END
      |         (Comparison's output already carries its own inline source
      |          citations per the required JSON schema — no separate
      |          Citation Agent pass needed)
      |
      +-- intent=executive_summary
            --> Retrieval --> Comparison (smart) --> Summary (smart) --> END

Comparison runs before Summary for executive_summary requests because a
grounded, well-ranked summary is far stronger when built on structured
diff/missing/match rows rather than raw retrieved text (see
summary_agent.py docstring).

Model tiering: the Router Agent — the user's first-touch interaction —
runs on the FAST/cheap model tier purely to classify intent. Everything
downstream that actually has to reason over retrieved document content and
produce the cited, structured deliverable (Comparison, Summary, Response,
Validation) runs on the SMART tier. See openai_client.py's ModelTier docs.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.application.agents.citation_agent import CitationAgent
from app.application.agents.comparison_agent import ComparisonAgent
from app.application.agents.response_agent import ResponseAgent
from app.application.agents.retrieval_agent import RetrievalAgent
from app.application.agents.router_agent import RouterAgent
from app.application.agents.state import GraphState
from app.application.agents.summary_agent import SummaryAgent
from app.application.agents.validation_agent import ValidationAgent
from app.infrastructure.ai.llm_gateway import LLMGateway, get_llm_gateway
from app.infrastructure.vectordb.pinecone_client import PineconeVectorStore


def _route_after_retrieval(state: GraphState) -> str:
    intent = state["intent"]
    if intent in ("compare_documents", "executive_summary"):
        return "comparison"
    return "response"


def _route_after_comparison(state: GraphState) -> str:
    return "summary" if state["intent"] == "executive_summary" else "__end__"


def build_graph():
    llm = get_llm_gateway()
    store = PineconeVectorStore()

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
        _route_after_retrieval,
        {"comparison": "comparison", "response": "response"},
    )

    graph.add_conditional_edges(
        "comparison",
        _route_after_comparison,
        {"summary": "summary", "__end__": END},
    )

    graph.add_edge("summary", END)
    graph.add_edge("response", "validation")
    graph.add_edge("validation", "citation")
    graph.add_edge("citation", END)

    return graph.compile()


_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
