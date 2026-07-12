"""
Shared graph state. This is the single object every agent reads from and
writes to as it flows through the graph. Kept as a TypedDict (not a class
with methods) because that's what LangGraph's StateGraph expects for
reducer-based merging between nodes.
"""
from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict

from app.domain.entities.document import Citation


class ConversationTurn(TypedDict):
    role: Literal["user", "assistant"]
    content: str


IntentType = Literal["single_doc_chat", "cross_doc_chat", "compare_documents", "executive_summary"]


class GraphState(TypedDict, total=False):
    # --- input ---
    user_query: str
    document_ids: list[str]  # 1 doc -> single chat; 2 docs -> cross/compare
    conversation_history: list[ConversationTurn]
    conversation_summary: str  # compressed memory of older turns

    # --- routing ---
    intent: IntentType
    routing_rationale: str

    # --- retrieval ---
    retrieved_chunks: list[dict]  # raw hits from Pinecone (post-rerank)
    expanded_context: str  # parent chunks stitched together, token-budgeted

    # --- comparison (only for compare_documents intent) ---
    comparison_report: Any  # ComparisonReport — kept as Any here to avoid a domain->state import cycle

    # --- summary (only for executive_summary intent) ---
    executive_summary: dict[str, Any]

    # --- generation ---
    draft_answer: str
    draft_citations: list[Citation]

    # --- validation ---
    is_grounded: bool
    grounding_warnings: list[str]
    confidence: float

    # --- final ---
    final_answer: str
    final_citations: list[Citation]

    # --- observability ---
    request_id: str
    agent_trace: list[str]  # ordered log of which agents ran, for debugging/observability
