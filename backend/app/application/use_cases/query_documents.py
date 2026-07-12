"""
Application use case: QueryDocuments.

This is the boundary between Presentation (FastAPI routes) and the agent
graph. Controllers must stay thin per the assignment's Clean Architecture
requirement — this is where request DTOs get turned into GraphState, the
graph gets invoked, and GraphState gets turned back into a response DTO.
"""
from __future__ import annotations

import uuid

from app.application.agents.graph import get_compiled_graph
from app.application.agents.state import GraphState
from app.application.dto.schemas import QueryRequest, QueryResponse
from app.infrastructure.ai.openai_client import OpenAIGateway
from app.infrastructure.repositories.conversation_memory import ConversationMemoryStore

_llm = OpenAIGateway()
_memory = ConversationMemoryStore(_llm)


async def execute(request: QueryRequest) -> QueryResponse:
    request_id = str(uuid.uuid4())
    summary, history = _memory.get_context(request.session_id)

    initial_state: GraphState = {
        "user_query": request.query,
        "document_ids": request.document_ids,
        "conversation_history": history,
        "conversation_summary": summary,
        "request_id": request_id,
        "agent_trace": [],
    }

    graph = get_compiled_graph()
    final_state: GraphState = await graph.ainvoke(initial_state)

    await _memory.add_turn(request.session_id, "user", request.query)

    intent = final_state["intent"]
    comparison_dict = None
    if intent in ("compare_documents", "executive_summary") and final_state.get("comparison_report"):
        comparison_dict = final_state["comparison_report"].to_dict()

    if intent == "compare_documents":
        answer_text = _render_comparison_as_text(final_state)
    elif intent == "executive_summary":
        answer_text = _render_summary_as_text(final_state)
    else:
        answer_text = final_state.get("final_answer") or final_state.get("draft_answer", "")

    await _memory.add_turn(request.session_id, "assistant", answer_text)

    return QueryResponse(
        request_id=request_id,
        intent=intent,
        answer=answer_text,
        citations=[c.__dict__ for c in final_state.get("final_citations", [])],
        comparison=comparison_dict,
        executive_summary=final_state.get("executive_summary"),
        is_grounded=final_state.get("is_grounded", True),
        confidence=final_state.get("confidence", 1.0),
        warnings=final_state.get("grounding_warnings", []),
        agent_trace=final_state.get("agent_trace", []),
    )


def _render_comparison_as_text(state: GraphState) -> str:
    report = state.get("comparison_report")
    if not report:
        return "No comparable content was found."
    lines = []
    for d in report.diff:
        lines.append(f"[DIFF] {d.reason}\n  A ({d.sourceA}): {d.docA_text}\n  B ({d.sourceB}): {d.docB_text}")
    for m in report.missing:
        lines.append(f"[MISSING] {m.text} — only in {m.source_file} ({m.location})")
    for m in report.match:
        lines.append(f"[MATCH] {m.source}")
    return "\n\n".join(lines) if lines else "No comparable content was found."


def _render_summary_as_text(state: GraphState) -> str:
    summary = state.get("executive_summary", {})
    if not summary:
        return "Unable to generate an executive summary from the available content."
    changes = "\n".join(
        f"{c['rank']}. [{c['severity'].upper()}] {c['title']}: {c['description']}"
        for c in summary.get("top_important_changes", [])
    )
    return (
        f"Top Important Changes:\n{changes}\n\n"
        f"Business Impact: {summary.get('business_impact', '')}\n\n"
        f"Architecture Impact: {summary.get('architecture_impact', '')}\n\n"
        f"Workflow Impact: {summary.get('workflow_impact', '')}"
    )
