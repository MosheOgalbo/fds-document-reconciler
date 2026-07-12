# FDS AI Platform — Semantic Document Reconciliation

AI system that compares two versions of a Functional Design Specification
(one PDF, one DOCX), detects what changed and what's missing, and lets
Product Managers query each document individually or ask cross-document
questions — with a ranked executive summary of the most important changes.

Built against the actual take-home brief (`AI_Engineer_Challenge.docx`,
included in this repo) and tested against the real sample files
(`samples/FDS_PriceBook_Automation_V0.pdf` and `_V5.docx`).

## Table of contents

- [Quick usage](#quick-usage)
- [Setup — native](#setup--native)
- [Setup — Docker](#setup--docker)
- [Environment variables](#environment-variables)
- [Architecture overview](#architecture-overview)
- [Model & provider choices](#model--provider-choices)
- [Two-tier model routing](#two-tier-model-routing)
- [Chunking & embedding](#chunking--embedding)
- [Retrieval](#retrieval)
- [Cross-document retrieval strategy](#cross-document-retrieval-strategy)
- [Document Comparison Engine — exact output format](#document-comparison-engine--exact-output-format)
- [Executive Summary — Top 10 ranking](#executive-summary--top-10-ranking)
- [Memory](#memory)
- [Validation (anti-hallucination)](#validation-anti-hallucination)
- [Security](#security)
- [Testing](#testing)
- [Known limitations](#known-limitations)
- [What I'd improve with more time](#what-id-improve-with-more-time)

---

## Quick usage

```bash
# 1. Ingest both sample documents
curl -X POST http://localhost:8000/api/v1/ingest \
  -F "file=@samples/FDS_PriceBook_Automation_V0.pdf" \
  -F "document_name=FDS_PriceBook_V0.pdf" \
  -F "version=v0"
# -> returns {"document_id": "<id-A>", ...}

curl -X POST http://localhost:8000/api/v1/ingest \
  -F "file=@samples/FDS_PriceBook_Automation_V5.docx" \
  -F "document_name=FDS_PriceBook_V5.docx" \
  -F "version=v5"
# -> returns {"document_id": "<id-B>", ...}

# 2. Compare them
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-1",
    "query": "Compare the pricing and process changes between versions",
    "document_ids": ["<id-A>", "<id-B>"]
  }'
# -> {"intent": "compare_documents", "comparison": {"missing": [...], "diff": [...], "match": [...]}, ...}

# 3. Ask a single-document question
curl -X POST http://localhost:8000/api/v1/query \
  -d '{"session_id": "demo-1", "query": "What is Phase A?", "document_ids": ["<id-A>"]}'

# 4. Ask a cross-document question
curl -X POST http://localhost:8000/api/v1/query \
  -d '{"session_id": "demo-1", "query": "What changed in the NA uplift rules between versions?", "document_ids": ["<id-A>", "<id-B>"]}'

# 5. Get the executive summary
curl -X POST http://localhost:8000/api/v1/query \
  -d '{"session_id": "demo-1", "query": "Give me the executive summary", "document_ids": ["<id-A>", "<id-B>"]}'
```

One endpoint (`/api/v1/query`) serves all three chat/compare/summary modes —
the Router Agent decides internally which workflow runs (see
[Architecture overview](#architecture-overview)); the API surface stays
thin per Clean Architecture.

## Setup — native

Requires Python 3.13+ (3.12 also verified working).

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real OPENAI_API_KEY / PINECONE_API_KEY
uvicorn app.main:app --reload --port 8000
```

**Frontend** (React 19 + TypeScript + Vite + Tailwind), in a second terminal:

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL, defaults to http://localhost:8000
npm run dev             # http://localhost:5173
```

`npm run build` runs `tsc -b && vite build` — TypeScript strict mode, verified
to compile cleanly with zero errors/warnings.

## Setup — Docker

```bash
docker compose up --build
```

Builds and runs the backend on `http://localhost:8000` and the frontend on
`http://localhost:5173`.

## Environment variables

See `backend/.env.example` for the full template. Key ones:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | Smart-tier fallback if GPT-5 isn't available (`gpt-4.1`) |
| `OPENAI_FAST_MODEL` | Fast-tier fallback (`gpt-4.1-mini`) |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-large` |
| `PINECONE_API_KEY` / `PINECONE_INDEX` | Vector store config (auto-creates index if missing) |
| `RETRIEVAL_TOP_K` / `RERANK_TOP_N` | Retrieval breadth vs. precision |
| `MAX_CONTEXT_TOKENS` | Token budget for context injected into prompts |
| `CONVERSATION_SUMMARY_TRIGGER_TURNS` | When conversation memory starts compressing |
| `RATE_LIMIT_RPM` | Requests/minute per client IP |

**Where do I actually put my API keys?** `backend/.env` — copy it from
`backend/.env.example` and fill in `OPENAI_API_KEY` and `PINECONE_API_KEY`,
then restart the backend. If you forget, you won't have to guess: the
frontend checks `GET /health` on every page load and shows a specific
banner naming exactly which key is missing and exactly which file to edit
— it won't let you discover this via a cryptic error mid-query.

## Architecture overview

Clean Architecture — see `docs/02_Architecture.md` for the full comparison
against Hexagonal and Modular Monolith alternatives, and `DECISIONS.md` for
the numbered decision log.

```
Presentation  (FastAPI routes, middleware)          — no business logic
    v
Application   (LangGraph agents, use cases, DTOs)   — orchestration
    v
Domain        (entities, exceptions)                — pure, dependency-free
    ^
Infrastructure (OpenAI, Pinecone, parsers, security) — implements interfaces
```

7-agent LangGraph workflow (full diagrams in `docs/03_System_Architecture.md`,
every agent documented individually in `AGENTS.md`):

```
Router (fast model) --> Retrieval --+-- single/cross-doc chat --> Response (smart) --> Validation (smart) --> Citation --> answer+citations
                                     |
                                     +-- compare_documents --> Comparison (smart) --> {missing, diff, match}
                                     |
                                     +-- executive_summary --> Comparison (smart) --> Summary (smart) --> Top-10 ranked changes
```

## Model & provider choices

**LLM:** OpenAI, resolved at runtime — GPT-5 if the account has access,
else GPT-4.1 — per the brief. `OpenAIGateway.resolve_model()` checks
`models.list()` against the live account rather than hardcoding, so the
system self-upgrades the moment access is granted, no code change needed.

**Embeddings:** `text-embedding-3-large` — strong general-purpose retrieval
quality at a 3072-dim vector, matched to Pinecone's index dimension config.

**Vector DB — Pinecone:** chosen over Chroma/FAISS/Qdrant because (a) it's
fully managed (no local index-persistence concerns for a Docker-delivered
take-home), (b) its metadata filtering (`$in`, `$eq`) is exactly what the
chosen cross-document retrieval strategy needs, (c) serverless indexes
auto-scale without capacity planning for a ~50-page-scale demo. FAISS would
require managing persistence/serialization ourselves; Chroma/Qdrant are
equally valid choices for this scale — Pinecone was picked for the
managed-service convenience, not because the others are worse.

## Two-tier model routing

Per explicit design request: the user's **first-touch interaction** (intent
classification in the Router Agent) runs on a **fast, cheap model**. Once
routed, retrieved vector context is handed to the **smart, capable model**
that performs the actually-required work — comparison, executive summary,
grounded response generation, and grounding validation.

```python
# app/infrastructure/ai/openai_client.py
_MODEL_CHAINS: dict[ModelTier, list[str]] = {
    "fast":  ["gpt-5-mini", "gpt-4.1-mini", "gpt-4.1-nano"],  # Router, conversation summarization
    "smart": ["gpt-5", "gpt-4.1"],                             # Comparison, Summary, Response, Validation
}
```

Each tier resolves independently against the live account's available
models — see `DECISIONS.md` D-06. This keeps cost/latency low on the
high-volume, low-complexity classification step while reserving expensive
calls for where they matter: reasoning over two documents' worth of
retrieved content and producing cited, structured output.

## Chunking & embedding

Heading-aware, hierarchical chunking (`infrastructure/parsing/chunker.py`)
— not fixed-size splitting — because citations must point to a real
section/page, and fixed-size splitting destroys that.

- **Parent chunks** (~1600 tokens): full section context, fetched by ID at
  generation time.
- **Child chunks** (~400 tokens, overlapping): what's actually embedded and
  searched — small chunks embed with less topic dilution than large ones.
- **Tables are preserved**, not flattened into garbled prose: PDF tables
  via `pdfplumber.extract_tables()`, DOCX tables via body-order XML
  iteration (`_iter_docx_block_items`) so a table stays in its correct
  position relative to surrounding paragraphs. Both convert to Markdown.
  This matters concretely here — the sample documents are Price Books;
  the actual business rules (uplift percentages, discount tiers) live in
  tables, not prose.

**Verified against the real sample files** (not just synthetic test data):
running the parser+chunker against `FDS_PriceBook_Automation_V0.pdf` surfaced
and fixed two real bugs — see [Known limitations](#known-limitations).

## Retrieval

Dense vector search (child chunks) + a lightweight lexical-overlap rerank
boost, then parent-expansion, dedup, and token-budget trimming. See
`docs/03_System_Architecture.md` "Retrieval Flow" for the diagram and
[Known limitations](#known-limitations) for what a production reranker
upgrade would look like.

## Cross-document retrieval strategy

**Chosen: a single Pinecone index, separated by metadata** (`document_id`,
`version`), not dual retrieval with separate indexes/queries per document.

A cross-document question issues **one** filtered vector query:
`filter={"document_id": {"$in": [doc_a_id, doc_b_id]}}` — Pinecone returns a
single ranked result set spanning both documents, which the Retrieval Agent
then expands/dedupes. See `DECISIONS.md` D-03 for why this was preferred
over dual retrieval at this document count/scale (dual retrieval would earn
back its extra round-trip and manual merge step at a much larger,
independently-scaled document count — not at two ~50-page specs).

## Document Comparison Engine — exact output format

The Comparison Agent (`application/agents/comparison_agent.py`) is
schema-constrained via OpenAI's `json_schema` structured output (`strict:
true`) to return **exactly**:

```json
{
  "missing": [{ "text": "...", "source_file": "docA.pdf", "location": "Page 12, Section 3.1" }],
  "diff":    [{ "docA_text": "...", "docB_text": "...", "reason": "...", "sourceA": "...", "sourceB": "..." }],
  "match":   [{ "textA": "...", "textB": "...", "source": "docA.pdf / Page 2 + docB.docx / Page 2" }]
}
```

Every item's source location is drawn from the retrieved chunk's real
citation header (`[document | section | page N]`) — the system prompt
explicitly forbids fabricating a location or file name; if a real citation
can't be pinned down for a claim, that claim is dropped rather than guessed.

## Executive Summary — Top 10 ranking

Schema-enforced `maxItems: 10` on `top_important_changes`, each item
carrying a `rank` (1–10) and a `ranking_rationale` explaining *why* it
ranks there in terms of business/architecture/workflow impact. The system
prompt explicitly forbids ranking by document position or chronology, and
the response is defensively re-sorted server-side by `rank` rather than
trusting model output order verbatim (`summary_agent.py`).

## Memory

`ConversationMemoryStore` (`infrastructure/repositories/conversation_memory.py`)
keeps recent chat turns verbatim per `session_id` and compresses older
turns into a running summary (fast model tier) once
`CONVERSATION_SUMMARY_TRIGGER_TURNS` is exceeded.

**Retrieved document knowledge and conversation memory are never merged
into one blob.** Every agent's system prompt states explicitly that
retrieved knowledge outranks conversation history if they ever conflict —
memory is background continuity, not a knowledge source. Currently
in-process (a Python dict) — see [Known limitations](#known-limitations)
for the production swap.

## Validation (anti-hallucination)

Two layers, cheapest first (`validation_agent.py`):

1. **Structural check** (no LLM call): every citation's `chunk_id` must
   exist in the chunks actually retrieved for this request — instantly
   catches fabricated citations.
2. **LLM-as-judge semantic check** (smart tier): verifies every claim in
   the draft answer is directly entailed by the retrieved source context;
   returns `is_grounded`, `confidence`, and specific unsupported claims.

If either check fails, the API surfaces `is_grounded: false` and the
Response Agent's answer falls back to "insufficient information" rather
than the possibly-hallucinated draft. This check applies to the free-text
chat path; Comparison/Summary already enforce per-item citations via their
structured-output schema directly.

## Security

- **Prompt injection screening** (`infrastructure/security/prompt_injection.py`):
  heuristic pre-screen on the router agent, plus — the actual primary
  defense — all retrieved document content is wrapped in explicit
  `<untrusted_document_content>` delimiters in every agent prompt, so
  injected text embedded inside a source document is treated as data to
  analyze, never as instructions to follow.
- Rate limiting (in-memory sliding window per client IP), request
  timeouts + exponential-backoff retries on all OpenAI calls, no secrets
  ever hardcoded (`.env.example` template only).
- **Global exception handler**: unhandled errors (OpenAI/Pinecone SDK
  failures, unexpected bugs) never leak raw internal details to the client
  — logged server-side against a `request_id`, sanitized message returned.
- **Middleware order is deliberate**: CORS is the outermost middleware so
  it can answer preflight `OPTIONS` requests before rate limiting ever
  sees them, and so CORS headers reach every response — including error
  responses. Both this ordering and a subtler gap (CORS headers missing
  specifically on responses from the global exception handler, a known
  Starlette/`BaseHTTPMiddleware` interaction) were found by testing the
  actual middleware stack with real HTTP requests, not just testing route
  handlers in isolation — see `DECISIONS.md` D-13/D-14 and
  `tests/api/test_error_handling.py`.

## Frontend

React 19 + TypeScript + Vite + Tailwind, built after the backend was
verified working (per the assignment's own development order). Four pages
sharing one layout (`AppShell` + `Sidebar`):

| Page | Route | Purpose |
|---|---|---|
| Documents | `/` | Ingest Document A/B (drag-drop, react-hook-form + zod validation) |
| Compare | `/compare` | Runs `compare_documents`, renders `{missing, diff, match}` as tabbed cards with a proportional "reconciliation bar" |
| Ask | `/chat` | Single-doc (A/B) or cross-document chat, citations rendered per message, grounding status surfaced visibly. Comparison/summary-style questions render as structured `InlineComparisonCard`/`InlineSummaryCard` components right in the conversation, not flattened text (see `DECISIONS.md` D-15) |
| Executive Summary | `/summary` | Top-10 ranked changes, each showing its `ranking_rationale`, plus business/architecture/workflow impact cards |

**State:** `DocumentsProvider` (React Context + `localStorage`) tracks the
two ingested documents across pages/reloads; TanStack Query handles all
server state (loading/error/retry) for ingest and query calls.

**Configuration visibility:** `ConfigurationBanner` polls `GET /health` on
load and shows a specific, unmissable banner if `OPENAI_API_KEY` or
`PINECONE_API_KEY` isn't configured (naming exactly which one and exactly
which file to edit), or if the backend is unreachable at all — see
`DECISIONS.md` D-18.

**Design system:** deliberately not the generic "AI app" cream+terracotta
look — a ledger/reconciliation-audit palette (deep ink navy, warm brass
accent, semantic match/diff/missing colors) with a serif display face
(`Source Serif 4`) for headings, a grotesk body face (`IBM Plex Sans`), and
a monospace utility face (`IBM Plex Mono`) for citations/chunk references —
fitting a Price Book/ledger reconciliation tool. The signature element is
the reconciliation bar: a proportional stacked bar (not decoration — it
encodes the real match/diff/missing ratio) reused as the visual anchor of
the Compare page.

**Verified, not just written:** `npm run build` (`tsc -b && vite build`,
TypeScript strict mode) compiles with zero errors; `npm run dev` starts
cleanly. See `frontend/` for the full source.

## Testing

```bash
cd backend
pytest -v                    # all 32 tests
pytest tests/unit -v         # pure logic, no API keys required
pytest tests/integration -v  # agent contracts + full-graph e2e via fakes, no API keys required
pytest tests/api -v          # FastAPI TestClient smoke tests + error-handling regression tests
```

32 tests pass, covering: hierarchical chunking (including two regression
tests for real bugs found against the actual sample PDF), table Markdown
formatting, token counting/context-window truncation (with fallback
verified), prompt-injection screening, citation dedup/verification, the
exact Comparison Engine JSON contract, **full end-to-end graph runs through
all 4 intents** (single-doc chat, cross-doc chat, compare, executive
summary — using the real compiled LangGraph with fakes, not just isolated
agent units), and API-level error handling (sanitized 500s, CORS headers
on error responses, CORS preflight behavior, backend configuration status).

Beyond the automated suite, the full ingestion pipeline (parse → chunk →
embed → upsert) and the full retrieval pipeline (query → rerank → parent-
expansion → token-budget trimming) were both run end-to-end against the
**actual sample files** in `samples/` — see `DECISIONS.md` D-16 for exact
results (chunk counts, zero missing embeddings, zero empty-content chunks).

## Known limitations

- **Token counting depends on network access to tiktoken's vocabulary
  file.** `count_tokens()`/`truncate_to_token_budget()` (`app/core/tokens.py`)
  use the real `tiktoken` tokenizer for exact context-window budgeting, but
  `tiktoken` fetches its encoding file from a remote URL on first use. In a
  network-restricted environment without egress to that host, it falls back
  automatically to a char/4 approximation (logged clearly, never crashes) —
  `GET /health`'s `token_counting` field reports which mode is active. This
  was discovered and verified firsthand: this development sandbox itself
  can't reach that host, so the fallback path is exercised, not just coded.
- **Heading detection has one confirmed false-positive case**: the sample
  PDF's "File Hierarchy" table (a borderless, numbered list of 13 rows) is
  short enough and capitalized enough to pass the heading heuristic and
  gets misidentified as 12 spurious sub-headings. Fixing this fully would
  need font-size/layout metadata (not exposed by plain text extraction) or
  a more elaborate table-vs-heading classifier — flagged here rather than
  papered over with a fragile ad-hoc rule. Two other real bugs found via
  the same testing process (trailing-period headings like "1. Executive
  Summary" being missed entirely, and line-wrapped body text starting with
  a bare number being falsely detected as a heading) **were** fixed and
  covered with regression tests.
- **DOCX page numbers are approximate** — `python-docx`'s object model has
  no native page-boundary concept; citations for DOCX sources rely
  primarily on section/heading, with page treated as best-effort.
- **Reranking** uses a lexical-overlap boost on top of vector similarity,
  not a dedicated cross-encoder reranker (e.g. Cohere Rerank). The
  `RetrievalAgent._rerank()` method is isolated specifically so swapping in
  a real reranker is a one-method change.
- **Conversation memory and rate limiting are in-process** (Python
  dict/deque), not shared across multiple backend replicas — fine for this
  take-home's single-instance scope; production would move both to Redis
  behind the same interface.
- **No offline RAG evaluation harness** (recall@k, groundedness scoring
  against a labeled Q&A set) — the Validation Agent's LLM-judge substitutes
  for this at request time, but a proper eval suite would run this offline
  against a golden dataset.
- **MCP, OpenTelemetry, Prometheus metrics** — deliberately not built; the
  actual brief doesn't request them (see `DECISIONS.md` D-08).

## What I'd improve with more time

- A real cross-encoder reranker instead of the lexical-overlap stand-in.
- A font-size/layout-aware heading classifier (e.g. using `pdfplumber`'s
  character-level bounding boxes) to eliminate the remaining table/heading
  false-positive case rather than just documenting it.
- Redis-backed memory + rate limiting for multi-instance deployments.
- An offline RAG evaluation harness with a golden Q&A set for this exact
  Price Book document pair.
- The React frontend (diff table view, chat UI, executive summary
  dashboard) — backend was prioritized per the assignment's own
  development order.

## Project documents

- `docs/01_Requirement_Analysis.md` — full requirement traceability
- `docs/02_Architecture.md` — architecture alternatives comparison
- `docs/03_System_Architecture.md` — Mermaid diagrams (component, sequence, per-flow)
- `AGENTS.md` — every agent explained
- `MEMORY.md` — project goals, business rules, standards
- `DECISIONS.md` — numbered architectural decision log
