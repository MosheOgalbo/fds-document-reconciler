# AGENTS.md

Every agent in the LangGraph workflow, in execution order, with its single
responsibility, model tier, inputs, and outputs. See `docs/03_System_Architecture.md`
for the visual flow.

## Router Agent
**File:** `app/application/agents/router_agent.py`
**Model tier:** fast (cheap/small model)
**Responsibility:** Classify the user's query into exactly one of 4 intents
(`single_doc_chat`, `cross_doc_chat`, `compare_documents`,
`executive_summary`). Also runs prompt-injection heuristic screening on the
raw query before anything else touches it.
**In:** `user_query`, `document_ids`
**Out:** `intent`, `routing_rationale`
**Why fast tier:** this is the user's first-touch interaction — a pure
classification task that doesn't require deep reasoning over document
content, so it's the cheapest place in the pipeline to spend tokens.

## Retrieval Agent
**File:** `app/application/agents/retrieval_agent.py`
**Model tier:** n/a (embedding call only, no chat completion)
**Responsibility:** Embed the query, run vector search filtered by
`document_ids`, rerank, expand surviving hits to their parent chunks,
dedupe, and trim to the token budget.
**In:** `user_query`, `document_ids`
**Out:** `retrieved_chunks`, `expanded_context`

## Comparison Agent
**File:** `app/application/agents/comparison_agent.py`
**Model tier:** smart (larger/more capable model)
**Responsibility:** Produce the Document Comparison Engine output in the
exact required schema: `{missing, diff, match}`, each item citation-backed
and explained. This is where the model has to read two documents' worth of
context and reason carefully — the reason it runs on the smart tier.
**In:** `expanded_context`, `user_query`
**Out:** `comparison_report`

## Summary Agent
**File:** `app/application/agents/summary_agent.py`
**Model tier:** smart
**Responsibility:** Produce the Executive Summary — Top 10 changes ranked
strictly by semantic/business importance (never document order), plus
business/architecture/workflow impact narratives. Runs after Comparison so
ranking is grounded in structured diff rows, not raw text.
**In:** `comparison_report` (or `expanded_context` as fallback)
**Out:** `executive_summary`

## Response Agent
**File:** `app/application/agents/response_agent.py`
**Model tier:** smart
**Responsibility:** Draft a grounded chat answer for single/cross-doc chat,
strictly from `expanded_context`. Conversation memory is included for
continuity only — retrieved knowledge always outranks it on conflict.
**In:** `expanded_context`, `conversation_history`, `conversation_summary`, `user_query`
**Out:** `draft_answer`, `draft_citations`

## Validation Agent
**File:** `app/application/agents/validation_agent.py`
**Model tier:** smart
**Responsibility:** Anti-hallucination gate. Structural check (citation
chunk_ids must exist in what was actually retrieved — no LLM call) plus an
LLM-as-judge semantic entailment check. Never rewrites the answer — only
flags `is_grounded`/`confidence`/`warnings` for the caller to act on.
**In:** `draft_answer`, `draft_citations`, `retrieved_chunks`, `expanded_context`
**Out:** `is_grounded`, `grounding_warnings`, `confidence`

## Citation Agent
**File:** `app/application/agents/citation_agent.py`
**Model tier:** n/a (deterministic, no LLM call)
**Responsibility:** Final dedup/verification pass on chat citations before
they reach the API — drops anything not in `retrieved_chunks`, dedupes by
document/version/section/page. (Comparison/Summary carry their own inline
source citations per the required schema and don't route through this
agent — see `graph.py` routing.)
**In:** `draft_citations`, `retrieved_chunks`
**Out:** `final_citations`
