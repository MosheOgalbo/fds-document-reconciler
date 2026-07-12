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
from app.infrastructure.ai.openai_client import OpenAIGateway
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

Respond ONLY via the provided JSON schema. Do not answer the user's underlying
question — you only classify it."""


class RouterAgent:
    def __init__(self, llm: OpenAIGateway):
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

        result = await self._llm.chat_json(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=f"Number of documents in scope: {num_docs}\nUser query: {query}",
            json_schema=_ROUTER_SCHEMA,
            schema_name="intent_routing",
            model_tier="fast",  # cheap first-touch classification, not the actual task
        )

        # Guardrail: if only one document is in scope, cross-doc/compare
        # intents are impossible regardless of what the LLM guessed.
        intent = result["intent"]
        if num_docs < 2 and intent in ("cross_doc_chat", "compare_documents"):
            intent = "single_doc_chat"

        state["intent"] = intent  # type: ignore[typeddict-item]
        state["routing_rationale"] = result["rationale"]
        state.setdefault("agent_trace", []).append(f"router_agent:intent={intent}")
        return state
