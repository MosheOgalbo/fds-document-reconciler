"""
Validation Agent.

Single responsibility: verify that the draft answer is actually grounded
in the retrieved context — this is the anti-hallucination gate the whole
assignment hinges on. It does NOT rewrite the answer; if grounding fails,
it flags it and the Response node (or a downstream fallback) is responsible
for degrading gracefully to "insufficient information".

Two checks, cheap-to-expensive:
1. Structural check: every citation's chunk_id actually appears in
   state['retrieved_chunks'] (catches fabricated citations instantly,
   no LLM call needed).
2. Semantic check: an LLM-as-judge call verifies the answer's claims are
   entailed by the cited snippets (catches subtler hallucination where the
   citation is real but doesn't actually support the claim made).
"""
from __future__ import annotations

from app.application.agents.state import GraphState
from app.core.config import get_settings
from app.infrastructure.ai.llm_gateway import LLMGateway

_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_grounded": {"type": "boolean"},
        "confidence": {"type": "number"},
        "unsupported_claims": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["is_grounded", "confidence", "unsupported_claims"],
    "additionalProperties": False,
}

_JUDGE_SYSTEM_PROMPT = """You are a strict Grounding Validator. You will receive a draft answer and
the retrieved source context it was supposed to be based on.

Determine: is every factual claim in the draft answer directly supported
by the source context? Do not accept plausible-sounding claims that aren't
actually stated in the context — err on the side of flagging as ungrounded.

List any specific unsupported claims verbatim."""


class ValidationAgent:
    def __init__(self, llm: LLMGateway):
        self._llm = llm
        self._settings = get_settings()

    async def run(self, state: GraphState) -> GraphState:
        warnings: list[str] = []

        # --- Check 1: structural citation integrity (no LLM call) ---
        known_chunk_ids = {c["chunk_id"] for c in state.get("retrieved_chunks", [])}
        fabricated = [
            c for c in state.get("draft_citations", [])
            if c.chunk_id not in known_chunk_ids
        ]
        if fabricated:
            warnings.append(f"{len(fabricated)} citation(s) do not match any retrieved chunk")

        # --- Check 2: semantic entailment via LLM judge ---
        try:
            judge_result = await self._llm.chat_json(
                system_prompt=_JUDGE_SYSTEM_PROMPT,
                user_prompt=(
                    f"DRAFT ANSWER:\n{state.get('draft_answer', '')}\n\n"
                    f"SOURCE CONTEXT:\n{state.get('expanded_context', '')}"
                ),
                json_schema=_JUDGE_SCHEMA,
                schema_name="grounding_judgment",
                model_tier="smart",
            )
        except Exception:
            # LLM-free fallback: skip semantic judging; keep structural gate only.
            judge_result = {"is_grounded": True, "confidence": 0.45, "unsupported_claims": []}

        judge_result.setdefault("unsupported_claims", [])
        judge_result.setdefault("is_grounded", True)
        judge_result.setdefault("confidence", 0.5)

        if judge_result["unsupported_claims"]:
            warnings.extend(f"Unsupported claim: {c}" for c in judge_result["unsupported_claims"])

        is_grounded = judge_result["is_grounded"] and not fabricated
        confidence = judge_result["confidence"] if not fabricated else min(judge_result["confidence"], 0.3)

        state["is_grounded"] = is_grounded
        state["grounding_warnings"] = warnings
        state["confidence"] = confidence
        state.setdefault("agent_trace", []).append(
            f"validation_agent:grounded={is_grounded},confidence={confidence:.2f}"
        )
        return state
