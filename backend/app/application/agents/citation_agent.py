"""
Citation Agent.

Single responsibility: take whatever citations survived validation and
produce the final, deduplicated, sorted citation list that goes out over
the API. This is intentionally a separate node (not folded into Response
or Validation) because citation formatting/dedup rules are a distinct
concern that changes independently — e.g. if the frontend later wants
citations grouped by document, that change lives entirely here.
"""
from __future__ import annotations

from app.application.agents.state import GraphState


class CitationAgent:
    async def run(self, state: GraphState) -> GraphState:
        citations = state.get("draft_citations", [])

        # Drop citations flagged as fabricated by validation (those whose
        # chunk_id wasn't in the retrieved set) — only keep verifiable ones.
        known_chunk_ids = {c["chunk_id"] for c in state.get("retrieved_chunks", [])}
        verified = [c for c in citations if c.chunk_id in known_chunk_ids]

        # Dedupe by (document_name, version, section, page) — same section
        # cited twice shouldn't show up twice in the UI.
        seen = set()
        deduped = []
        for c in verified:
            key = (c.document_name, c.version, c.section, c.page_number)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(c)

        deduped.sort(key=lambda c: (c.document_name, c.page_number))

        state["final_citations"] = deduped
        state.setdefault("agent_trace", []).append(f"citation_agent:final_count={len(deduped)}")
        return state
