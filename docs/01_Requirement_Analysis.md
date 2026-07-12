# Requirement Analysis

> Source of truth: `docs/00_Challenge_Brief.md` (verbatim copy of the
> `AI_Engineer_Challenge.docx` take-home brief) and the two sample documents
> `FDS_PriceBook_Automation_V0.pdf` (Doc A, older) and
> `FDS_PriceBook_Automation_V5.docx` (Doc B, newer, expanded). Every
> requirement below is traceable to that brief — nothing here is invented.

## Executive Summary

Build a system that ingests two versions of a Functional Design Spec
(one PDF, one DOCX), detects what changed/what's missing between them,
answers grounded questions about either document individually or across
both, and ranks the top-10 most important changes for an executive summary.
Everything must be traceable to a real citation — no hallucinated answers.

## Business Problem

Product Managers currently compare FDS versions manually — slow, error
prone, and with no consistent traceability back to source. The sample
documents themselves describe exactly this kind of problem in a different
domain (manual Price Book regeneration) — the assignment is, fittingly,
about automating manual document reconciliation.

## Business Goals

- Eliminate manual side-by-side document comparison.
- Guarantee every AI-generated claim is traceable to an exact source location.
- Give Product Managers a ranked, prioritized view of what actually matters
  in a large diff, not just a flat list of every change.

## Actors

- **Product Manager** — primary user; uploads document versions, asks
  questions, reads comparison output and executive summaries.
- **System / AI Agents** — ingest, retrieve, compare, summarize, validate.

## Functional Requirements

| ID | Requirement |
|---|---|
| FR-1 | Ingest PDF and DOCX, preserving headings, tables, and section hierarchy |
| FR-2 | Document Comparison Engine returning exactly `{missing, diff, match}` JSON, each item carrying a source citation and an LLM-written explanation |
| FR-3 | Single Document RAG chat — grounded, cited, no external knowledge |
| FR-4 | Cross-Document chat — queries both documents, synthesizes one answer, cites both sources |
| FR-5 | Executive Summary — Top 10 changes ranked by **semantic importance**, not chronology or document order |

## Non-Functional Requirements

- No single bare LLM call per query — multi-step/agent orchestration required (LangGraph).
- Structured Outputs enforced via the LLM provider's native mechanism (OpenAI `json_schema`, strict mode), not regex/prompt-only enforcement.
- Free choice of vector DB / LLM provider, justified in README.
- Dockerized, single-command build & run.
- No hardcoded secrets — `.env.example` template only.

## AI Requirements

- LLM: OpenAI, GPT-5 when available else GPT-4.1 (see `DECISIONS.md`).
- Two-tier model routing: fast/cheap model for first-touch intent
  classification, smart/capable model for the actual comparison/summary/
  response/validation work (see `DECISIONS.md` D-06).
- Embeddings: `text-embedding-3-large`.

## RAG Requirements

- Hierarchical, heading-aware chunking (not fixed-size splitting) — required
  because citations must point to a real section/page.
- Parent-child chunking: small chunks embedded/searched, larger parent
  context injected at generation time.
- Tables must be preserved as structured content, not flattened prose —
  critical because this is a Price Book: the actual business rules
  (prices, uplift percentages, discount tiers) live in tables.
- Single Pinecone index, metadata-partitioned by `document_id`/`version`
  (see cross-document retrieval strategy in README and `DECISIONS.md` D-03).

## Comparison Requirements

Exact output contract (verbatim from the brief):
```json
{
  "missing": [{ "text": "...", "source_file": "docA.pdf", "location": "Page 12, Section 3.1" }],
  "diff":    [{ "docA_text": "...", "docB_text": "...", "reason": "...", "sourceA": "...", "sourceB": "..." }],
  "match":   [{ "textA": "...", "textB": "...", "source": "docA.pdf / Page 2 + docB.docx / Page 2" }]
}
```

## Chat Requirements

- Single-doc and cross-doc modes share one API endpoint; the Router Agent
  decides which path runs internally (see `docs/02_Architecture.md`).
- Every chat answer must fail closed (say "insufficient information")
  rather than hallucinate when retrieved context doesn't support an answer.

## Executive Summary Requirements

- Exactly ranked Top 10 (schema-enforced `maxItems: 10`).
- Ranking must be justified per item (`ranking_rationale` field) in terms of
  business/architecture/workflow impact — never position-in-document.

## Constraints

- ~50-page document scale (per brief) — chunking/retrieval tuned for this,
  not for hundred-thousand-page corpora.
- ~4 hour target build time — architecture favors pragmatic, well-justified
  choices over exhaustive enterprise tooling (see `DECISIONS.md` for what
  was deliberately left out and why).

## Risks

- **Table extraction fidelity**: borderless/loosely-formatted tables in
  source PDFs can be mis-detected by plain-text heading heuristics (see
  README "Known limitations" — confirmed against the actual sample PDF).
- **DOCX page numbers are approximate** — the format has no native page
  model.
- **LLM-judge grounding check** is itself a model call, not a formal proof —
  it substitially reduces but does not mathematically eliminate hallucination risk.

## Technical Recommendations

- Keep Comparison/Summary/Response on the "smart" model tier; keep routing
  and housekeeping (conversation summarization) on the "fast" tier — this
  is the cost/quality split requested for this system.
- Treat MCP, OpenTelemetry, and Prometheus metrics as explicitly out of
  scope for this brief (not requested) — see `DECISIONS.md` D-08.

## Open Questions

- Should DOCX table rows that lack explicit column headers still render as
  Markdown tables with a synthetic header row, or as plain indented text?
  Current implementation always emits a Markdown table (first row treated
  as header) — reasonable default, flagged here for review.
- Is a single shared Pinecone index (chosen) preferred long-term over
  per-document indexes if the corpus grows well beyond ~50 pages/document?
  See `DECISIONS.md` D-03 for the tradeoff as currently understood.
