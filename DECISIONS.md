# DECISIONS.md

Numbered architectural decision log. Each entry: context, decision, alternatives, tradeoff.

## D-01: Clean Architecture over Hexagonal or Modular Monolith
**Context:** four required capabilities (comparison, single-doc chat,
cross-doc chat, executive summary) share almost the entire pipeline
(parsing → chunking → retrieval → generation).
**Decision:** Clean Architecture with domain/application/infrastructure/presentation layers.
**Alternatives considered:** Hexagonal (functionally near-identical, just
different vocabulary — not worth a separate migration); Modular Monolith
(feature-sliced) — would duplicate the shared pipeline or collapse back
into layers anyway. See `docs/02_Architecture.md` for full comparison.

## D-02: LangGraph multi-agent graph, not a single LLM call
**Context:** brief explicitly states "a single LLM call per query is not
sufficient" and requires an agent loop or multi-step retrieval.
**Decision:** 7-node LangGraph state machine (Router → Retrieval →
Comparison/Response → Summary/Validation → Citation), conditional routing
by intent.
**Alternative considered:** a hand-rolled orchestration loop without
LangGraph — rejected because LangGraph's conditional edges + typed state
give the same behavior with less bespoke plumbing and a visualizable graph
(`graph.get_graph().draw_mermaid()`).

## D-03: Single Pinecone index, metadata-partitioned — chosen cross-document retrieval strategy
**Context:** brief explicitly asks the README to describe the
cross-document retrieval strategy — shared index w/ metadata vs. dual
retrieval.
**Decision:** one Pinecone index; every chunk carries `document_id` and
`version` in metadata; cross-document queries pass
`document_ids: {"$in": [...]}` as a single filtered query.
**Why not dual retrieval (querying each document's index separately then
merging):** at this document count/scale, dual retrieval adds a second
round-trip and a manual result-merging/reranking step for no retrieval-
quality benefit — a single filtered query already returns ranked results
across both documents in one call. Dual retrieval would earn its
complexity back at a much larger number of independently-scaled documents,
not at two ~50-page specs.

## D-04: Parent-Child chunking over flat fixed-size chunking
**Context:** citations must point to an exact section/page; small chunks
embed better (less topic dilution) but lose surrounding context needed for
generation.
**Decision:** heading-aware chunker produces PARENT chunks (~1600 tokens,
full section context) and CHILD chunks (~400 tokens, overlapping, what's
actually embedded/searched); a hit on a child expands to its parent for
generation.

## D-05: Tables extracted as Markdown, interleaved into the text stream
**Context:** these are Price Book specs — actual business rules (prices,
uplift %, discount tiers) live in tables; naive text extraction flattens
them into unreadable columns-as-prose.
**Decision:** `pdfplumber.extract_tables()` for PDF, XML-body-order
iteration (`iter_block_items`) for DOCX so `w:tbl` elements are converted to
Markdown in their correct document position, not appended out of order.
**Tradeoff documented:** borderless/loosely-structured tables can still be
misparsed by the heading heuristic (see README "Known limitations") —
confirmed against the actual sample PDF's File Hierarchy table.

## D-06: Two-tier model routing (fast vs. smart)
**Context:** user request — the first-touch interaction with the user
(intent classification) should run on the smallest model, with the
retrieved vector context then handed to a "smart" agent that performs the
actual required work.
**Decision:** `OpenAIGateway` resolves two independent model chains —
`fast: [gpt-5-mini, gpt-4.1-mini, gpt-4.1-nano]` for Router Agent +
conversation summarization; `smart: [gpt-5, gpt-4.1]` for
Comparison/Summary/Response/Validation. Each tier self-upgrades to GPT-5
the moment the API key has access, independently.

## D-07: Pragmatic DI (constructor injection at composition root) over a formal Protocol/ABC layer
**Context:** Clean Architecture usually implies agents depend on abstract
interfaces, with infrastructure classes as concrete implementations
injected in.
**Decision:** for this scale, agents take concrete `OpenAIGateway`/
`PineconeVectorStore` instances directly (constructed once in `graph.py`)
rather than defining separate `Protocol` interfaces for each.
**Tradeoff:** slightly less pure than textbook Clean Architecture; the
concrete classes' public methods are narrow enough to serve as a de-facto
interface, and tests already substitute fakes successfully
(`tests/integration/test_retrieval_agent.py`) without needing formal ABCs.
Revisit if the infrastructure layer grows multiple real implementations
per interface (e.g. Pinecone AND Qdrant simultaneously).

## D-08: MCP, OpenTelemetry, and Prometheus metrics — explicitly out of scope
**Context:** an earlier, unrelated "elite AI engineering team" style prompt
requested these; the actual take-home brief (`AI_Engineer_Challenge.docx`)
does not.
**Decision:** treat the actual brief as the sole source of truth per its
own instruction ("if your own ideas conflict with the specification, the
specification always wins") and do not build these. Structured logging +
request IDs (already implemented) satisfy the brief's own observability
expectations without the extra surface area.

## D-09: Exactly 3 comparison categories, restructured mid-project
**Context:** an initial implementation used 5 categories
(MATCH/MODIFIED/ADDED/REMOVED/MISSING) based on an earlier, less precise
version of the requirements.
**Decision:** once the actual brief's exact JSON schema was available
(`{missing, diff, match}`), the domain model and Comparison Agent were
rewritten to match it exactly, including field-level names (`docA_text`,
`sourceB`, etc.) rather than a paraphrased equivalent schema.
**Why this matters:** the brief states the output "must return results in
this exact JSON structure" — treated as a hard, non-negotiable contract,
not a suggestion to reinterpret.

## D-10: Parent-chunk expansion bug found and fixed during backend review
**Context:** a dedicated review pass (requested explicitly: "check that the
backend performs the task and agents are correctly defined") re-read every
agent against its actual data flow rather than just re-running existing
tests.
**Finding:** `DocumentChunk.to_metadata()` emitted a `parent_section` field
derived from `SectionPath.parent_section_id` — a field that was declared
but **never populated anywhere** in the chunker. The Retrieval Agent's
parent-expansion step read that same (always-empty) field, so
`fetch_parent()` was never actually invoked in practice — every query
silently fell back to raw child-chunk content only, defeating the entire
parent-child chunking design documented in the README.
**Fix:** removed the dead `parent_section_id` field; `to_metadata()` now
emits the chunk's real `parent_chunk_id`; Retrieval Agent updated to match.
The integration test that exercised this path was itself asserting against
the wrong field name (so it passed despite the bug) — rewritten to assert
against the real field and to verify `fetch_parent` is actually called
with the correct id.

## D-11: Citations were structurally uncitable — found and fixed
**Context:** same review pass, tracing the Response Agent's citation
schema back to what the model actually sees in its prompt.
**Finding:** the retrieved-context block headers shown to the LLM included
document/version/section/page — but never `chunk_id`. Since the Response
Agent's structured-output schema *requires* a `chunk_id` per citation, the
model had no way to supply a real one; it could only guess or omit,
meaning the Validation Agent's structural check (verifying `chunk_id`
against retrieved chunks) would have flagged the large majority of
otherwise-correct answers as ungrounded.
**Fix:** block headers now include `chunk_id: <id>` explicitly; the
Response Agent's system prompt instructs the model to copy it verbatim
rather than invent one. The Comparison Agent's prompt (which references
the same header format for its own location fields) was updated to match.

## D-12: React frontend built after backend review
**Context:** frontend requested only once backend correctness was verified.
**Decision:** React 19 + TypeScript + Vite + Tailwind, hand-built component
by component (not scaffolded via a template) so every file matches this
project's actual API contracts (`frontend/src/types/api.ts` mirrors the
backend DTOs directly). Verified with a real `npm install && npm run build`
— TypeScript strict mode compiles with zero errors — not just written and
assumed correct.

## D-13: Middleware order fixed + CORS-on-error gap found and fixed
**Context:** deeper professional-configuration review pass, testing the
actual middleware stack with real HTTP requests through `TestClient`
rather than only unit-testing route handlers in isolation.
**Finding 1 — middleware order:** `CORSMiddleware` was added first (=
innermost). Starlette applies the LAST-added middleware as outermost, so
this meant a CORS preflight (`OPTIONS`) request would reach
`RateLimitMiddleware` before `CORSMiddleware` ever got to handle it —
under load, a preflight could get rate-limited and never receive proper
CORS headers, breaking real cross-origin requests from the frontend.
**Fix 1:** reordered so `CORSMiddleware` is added last (= outermost).
Verified via `TestClient`: an actual `OPTIONS` preflight now returns 200
with correct `Access-Control-Allow-*` headers, and a request that
deliberately exceeds `RATE_LIMIT_RPM` still carries the CORS header on its
429 response.
**Finding 2 — CORS missing on unhandled-exception responses:** even after
fixing the ordering, a response generated by the global
`@app.exception_handler(Exception)` still lacked CORS headers — a known
Starlette interaction where `BaseHTTPMiddleware`-based middleware
(`RateLimitMiddleware`/`RequestContextMiddleware`, both used here) sitting
between the exception handler and `CORSMiddleware` can prevent the
CORS layer from processing that particular response. Reproduced with a
real `TestClient(raise_server_exceptions=False)` call before fixing.
**Fix 2:** the exception handler now attaches
`Access-Control-Allow-Origin` directly (echoing the request's `Origin`
header) as a defensive measure, rather than relying solely on
`CORSMiddleware`. Both findings are pinned down by regression tests in
`tests/api/test_error_handling.py`.

## D-14: Global exception handler added
**Context:** before this pass, `DomainError` was caught and translated to
clean 4xx responses at the route level, but anything else (an OpenAI SDK
error, a bug, an unexpected timeout) would propagate as a raw, unhandled
500 with FastAPI's default behavior — acceptable for local dev, not for a
system claiming production-readiness.
**Decision:** added `@app.exception_handler(Exception)` in `main.py`: logs
the full exception server-side against the request's `request_id`, and
returns a sanitized `{"detail": "...", "request_id": "..."}` body — never
the raw exception message — to the client.

## D-15: Chat renders structured task results as inline cards, not flattened text
**Context:** the backend's `/api/v1/query` endpoint already returns
structured `comparison`/`executive_summary` payloads for those intents
(D-09), but the frontend's chat view was only ever rendering
`result.answer` — a flattened text summary — even when the user asked a
comparison/summary-style question directly from the Ask page.
**Decision:** `ChatMessage` now renders `InlineComparisonCard` /
`InlineSummaryCard` — compact versions of the dedicated Compare/Summary
page views — directly inside the chat message flow whenever the response
carries that structured data, with a link out to the full page view. Plain
text is still shown for genuine single/cross-doc chat answers.
**Why this matters:** a separate, unrelated "generic multi-agent file
platform" system prompt was shared partway through this project, proposing
a completely different, incompatible output schema
(`task_metadata`/`extracted_data_and_insights`/etc.). That schema was not
adopted — it belongs to a different kind of system and conflicts with the
brief's own "exact JSON structure" requirement (D-09). What *was* adopted
from that conversation was the underlying, compatible idea: task results
should show up as styled components in chat, not just prose — implemented
here without touching the backend's existing, correct output contract.

## D-16: Full ingestion pipeline verified against the real sample files, not just synthetic tests
**Context:** requested verification that 2-file ingestion → chunking →
embedding → Pinecone storage actually works, not just that unit tests pass.
**Verification performed:** ran the real `ingest_document.execute()` use
case against both actual sample files (`FDS_PriceBook_Automation_V0.pdf`,
`FDS_PriceBook_Automation_V5.docx`) with only the OpenAI embedding call
mocked (no real API key available in this environment) — everything else
(parsing, chunking, metadata construction, the upsert call shape) ran for
real. Result: 77 chunks from the PDF (27 parent / 50 child), 95 from the
DOCX (36 parent / 59 child), zero chunks with missing embeddings, zero
chunks with empty content. Also ran a full retrieval pass against the real
resulting chunks (parent-expansion, context assembly, token-budget
trimming) and confirmed the expanded context correctly pulls full parent
section text, not just the small child snippet.
**Bug found in the process:** the citation header template hardcoded a
`v` prefix (`f"...{document} v{version}..."`), producing `"...vv0"` when a
user's own version label already started with `v` (a natural convention,
as used in this project's own examples). Fixed to `"{document} ({version})"`
— unambiguous regardless of the user's labeling convention.

## D-17: Token counting upgraded from char/4 approximation to real tiktoken counting, with graceful fallback
**Context:** context-window budgeting (`MAX_CONTEXT_TOKENS`) and chunk-size
decisions were both based on a `len(text) // 4` heuristic everywhere —
a reasonable rule of thumb, but not the model's actual tokenizer, and
budget enforcement is exactly the place where under-counting could
silently exceed the real context window.
**Decision:** added `app/core/tokens.py` — `count_tokens()` and
`truncate_to_token_budget()` — backed by `tiktoken`'s real `cl100k_base`
encoder, with a hard fallback to the char/4 approximation if the encoder
can't be loaded. This matters because `tiktoken` fetches its vocabulary
file from a remote URL on first use; a network-restricted environment
(discovered firsthand: this sandbox itself can't reach
`openaipublic.blob.core.windows.net`) would otherwise crash ingestion
entirely. Verified the fallback path directly: token counting and budget
truncation both continue to work, with a clear log message, when the
encoder is unavailable. Wired into the two places that matter most: the
stored per-chunk `token_count` metadata (chunker.py) and the actual
context-window truncation in `RetrievalAgent._trim_to_token_budget`
(previously a crude char-slice; now decodes the real token slice back to
text when the encoder is available).
**Deliberately NOT changed:** the word-by-word accumulation loop that
decides *where* to split a section into parent chunks still uses the cheap
per-word approximation — precision doesn't matter for a rough "~1600
token" boundary decision, and calling a real tokenizer once per word would
be needlessly slow on a large document.

## D-18: Backend configuration status surfaced explicitly to the user
**Context:** requested that it be clear to the user where to enter API
keys, rather than discovering a missing key via a downstream OpenAI/
Pinecone error during their first real request.
**Decision:** `/health` now reports `openai_configured`,
`pinecone_configured` (also treating the literal placeholder values from
`.env.example` as "not configured", not just an empty string), and
`token_counting` ("exact" vs "approximate", surfacing D-17's fallback
state). The frontend's `ConfigurationBanner` polls this on every page load
and shows a persistent, specific banner — naming exactly which env var is
missing and exactly which file to edit (`backend/.env`, copied from
`backend/.env.example`) — rather than a generic "something's wrong"
message. A second banner state covers the backend being unreachable
entirely (wrong `VITE_API_BASE_URL` or backend not running).
