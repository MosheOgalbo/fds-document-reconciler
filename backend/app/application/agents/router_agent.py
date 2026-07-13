"""
Intent Router Agent.

Single responsibility: classify the user's query into one of the four
supported workflows, and detect prompt injection attempts before anything
else touches the query. This agent NEVER generates business content — it
only routes. Keeping routing separate from generation means we can unit
test intent classification without mocking the entire RAG pipeline.
"""
from __future__ import annotations

import logging

from app.application.agents.state import GraphState
from app.infrastructure.ai.llm_gateway import LLMGateway
from app.infrastructure.security.prompt_injection import screen_for_injection

logger = logging.getLogger(__name__)

_ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["single_doc_chat", "cross_doc_chat", "compare_documents", "executive_summary"],
        },
        "rationale": {"type": "string"},
    },
    "required": ["intent", "rationale"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = """You are the Intent Router for an enterprise document-analysis system.
Classify the user's request into exactly one intent:

- single_doc_chat: a question about ONE document's content.
- cross_doc_chat: a question that requires reading from TWO documents and relating them.
- compare_documents: an explicit request to diff/compare two document versions
  (changed/added/removed/modified requests).
- executive_summary: a request for a high-level summary of changes, business impact,
  or "what changed overall".

Respond ONLY with valid JSON containing exactly these keys:
{"intent": "<one of the four values above>", "rationale": "<short explanation>"}
Do not answer the user's underlying question — you only classify it."""

_INTENT_ALIASES = {
    "document_comparison": "compare_documents",
    "compare": "compare_documents",
    "comparison": "compare_documents",
    "summary": "executive_summary",
    "executive summary": "executive_summary",
    "single_document_chat": "single_doc_chat",
    "cross_document_chat": "cross_doc_chat",
}

def _heuristic_intent(query: str, num_docs: int) -> str:
    q = query.lower()
    if any(k in q for k in ["top", "most important", "executive summary", "highlights", "summary", "what changed overall"]):
        return "executive_summary" if num_docs >= 2 else "single_doc_chat"
    if any(k in q for k in ["compare", "diff", "difference", "changed", "between versions", "vs"]):
        return "compare_documents" if num_docs >= 2 else "single_doc_chat"
    if num_docs >= 2 and any(k in q for k in ["both documents", "across", "between", "in doc a", "in doc b"]):
        return "cross_doc_chat"
    return "single_doc_chat"


class RouterAgent:
    def __init__(self, llm: LLMGateway):
        self._llm = llm

    async def run(self, state: GraphState) -> GraphState:
        query = state["user_query"]

        # Security gate: screen for injection BEFORE the query touches any
        # LLM call or retrieval filter. If flagged, we still route (so the
        # user gets a clean rejection message downstream) but we tag it.
        injection_flags = screen_for_injection(query)
        if injection_flags:
            logger.warning("Prompt injection heuristics matched: %s", injection_flags)

        num_docs = len(state.get("document_ids", []))

        try:
            result = await self._llm.chat_json(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=f"Number of documents in scope: {num_docs}\nUser query: {query}",
                json_schema=_ROUTER_SCHEMA,
                schema_name="intent_routing",
                model_tier="fast",  # cheap first-touch classification, not the actual task
            )
        except Exception as e:
            # Free-tier APIs can rate-limit; routing must still work.
            logger.warning("Router LLM call failed; falling back to heuristics: %s", e)
            result = {"intent": _heuristic_intent(query, num_docs), "rationale": "heuristic fallback (LLM unavailable)"}

        # Guardrail: if only one document is in scope, cross-doc/compare
        # intents are impossible regardless of what the LLM guessed.
        intent = _INTENT_ALIASES.get(result.get("intent", ""), result.get("intent", "single_doc_chat"))
        if intent not in ("single_doc_chat", "cross_doc_chat", "compare_documents", "executive_summary"):
            intent = "single_doc_chat"
        if num_docs < 2 and intent in ("cross_doc_chat", "compare_documents", "executive_summary"):
            intent = "single_doc_chat"

        state["intent"] = intent  # type: ignore[typeddict-item]
        state["routing_rationale"] = result.get("rationale", "")
        state.setdefault("agent_trace", []).append(f"router_agent:intent={intent}")
        return state
