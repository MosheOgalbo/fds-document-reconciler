# MEMORY.md

Project memory: what this system is, why it's built this way, and the
standards to keep applying if it's extended.

## Project goals

Automate manual FDS document reconciliation: detect what changed between
two spec versions, answer grounded questions about either or both, and
surface a prioritized executive summary — all with hard citation
traceability, per `AI_Engineer_Challenge.docx`.

## Business rules

- The Comparison Engine output MUST match the exact schema
  `{missing, diff, match}` — this came directly from the brief's "Required
  Output Format" section, not from our own design preference.
- Executive Summary MUST rank by semantic/business importance, explicitly
  NOT by chronological order or document position — stated twice in the
  brief, treated as a hard constraint (`maxItems: 10` + explicit prompt rule
  + a defensive server-side sort by `rank`, not trusting model output order).
- Every claim, in every mode, must trace to a real citation or the system
  must say "insufficient information" — no exceptions, no soft fallback to
  general knowledge.

## Architecture decisions

See `DECISIONS.md` for the full numbered log. Headline choices:
- Clean Architecture (domain/application/infrastructure/presentation).
- LangGraph multi-agent graph, not a single LLM call (explicit constraint).
- Single Pinecone index, metadata-partitioned by `document_id`/`version`
  (not per-document indexes) — enables cross-document queries in one call.
- Two-tier model routing: fast model for routing/housekeeping, smart model
  for actual comparison/summary/response/validation work.

## Coding standards

- `from __future__ import annotations` in every module for forward-ref typing.
- Every agent is a class with one public `async def run(state) -> state`
  method — same signature everywhere, so agents compose in the graph
  without special-casing.
- Domain entities are plain `@dataclass`, zero framework imports.
- Infrastructure clients (`OpenAIGateway`, `PineconeVectorStore`) lazily
  construct their underlying SDK client — importing/instantiating them must
  never require a real API key (this was an actual bug found via test
  collection failing; fixed by making the client a lazy property).
- Structured LLM output always goes through `chat_json(..., json_schema=...)`
  with `strict: true` — never parse free text for structured data.

## Naming conventions

- Agents: `<Name>Agent` in `app/application/agents/<name>_agent.py`, each
  with a module-level docstring explaining single responsibility.
- Domain exceptions: `<Thing>Error` subclassing `DomainError`.
- Use cases: verb_noun modules (`query_documents.py`, `ingest_document.py`)
  exposing a single `async def execute(...)`.

## Important constraints

- ~4 hour build target, ~50-page document scale — tuning (chunk sizes,
  retrieval top_k, token budgets) is calibrated for this scale, not
  arbitrarily large corpora.
- MCP, OpenTelemetry, and Prometheus metrics are explicitly OUT of scope —
  the actual brief doesn't request them (an earlier, unrelated "elite team"
  style prompt did, but the real challenge brief is the source of truth;
  see `DECISIONS.md` D-08).

## Design decisions carried forward

- Parent-child chunking, not flat fixed-size chunking — required for
  accurate page/section citations.
- Table content is extracted and rendered as Markdown, interleaved into the
  text stream — critical because this is a Price Book; the actual business
  rules live in tables, not prose.
- Heading detection uses a numeric-prefix regex PLUS a heuristic filter
  (max line length, capitalized title) — found and fixed two real bugs by
  testing against the actual sample PDF (trailing-period headings like
  "1. Executive Summary" were originally missed entirely; wrapped body text
  starting with a bare number was originally misdetected as a heading).
  A remaining known false-positive case (borderless numbered tables) is
  documented in README rather than papered over with a fragile heuristic.
