# AI Engineer · Take-Home Challenge — Semantic Document Reconciliation

> Verbatim content of `AI_Engineer_Challenge.docx`, the source-of-truth brief
> for this project. Saved here for provenance/traceability (see
> `docs/01_Requirement_Analysis.md` and `DECISIONS.md`).

~4 hours · 3 Deliverables · Docker delivery · ~50-page scale

Build an AI-powered system that compares two versions of a Functional
Design Specification (FDS) document — one PDF and one DOCX. The system
should detect what's changed, what's missing, and let users query each
document or ask cross-document questions.

## What to Build

**1. Document Comparison Engine**
Compare Document A (older) and Document B (newer). Output a structured
JSON result with three categories:
- **MATCH** — Sections that are identical or semantically equivalent
- **DIFF** — Sections that exist in both but have changed meaningfully
- **MISSING** — Content present in one document but absent from the other

Constraint: Each result must include a source citation (filename +
location) and a short LLM-generated explanation.

**2. RAG Chatbot — Single Document Mode**
A query interface where the user can ask questions about Document A or
Document B individually.
Constraint: Answers must use only retrieved context — no external
knowledge injection.
Constraint: Every answer must include precise citations (document name +
chunk/location).

**3. Cross-Document Chat Mode**
A query interface for comparative questions — e.g., "What changed in the
authentication flow between versions?"
Constraint: The system must query both documents simultaneously and
synthesize a response.
Constraint: Differences must be clearly highlighted with citations from
both sources.
README note: Describe your retrieval strategy (shared index with
metadata, dual retrieval, etc.) — this is an architectural decision, not
an implementation detail.

## Technical Requirements

| Component | What's Required |
|---|---|
| Vector Database | Any standard store (Chroma, FAISS, Qdrant, Pinecone, Weaviate…) — briefly justify your choice in the README. |
| Document Parsing | Must handle both .pdf and .docx, preserving headings, tables, and section hierarchy. |
| Orchestration | Include an agent loop or multi-step retrieval logic. A single LLM call per query is not sufficient. |
| Structured Output | Use Function Calling, Tool Use, or Structured Outputs to enforce the JSON schema on comparison results. |
| LLM Provider | Any provider (OpenAI, Anthropic, etc.). Document your model and embedding choices in the README. |

## Required Output Format

```json
{
  "missing": [{ "text": "...", "source_file": "docA.pdf", "location": "Page 12, Section 3.1" }],
  "diff":    [{ "docA_text": "...", "docB_text": "...", "reason": "...", "sourceA": "...", "sourceB": "..." }],
  "match":   [{ "textA": "...", "textB": "...", "source": "docA.pdf / Page 2 + docB.docx / Page 2" }]
}
```

Also build: An Executive Summary Generator that produces a "Top 10 Most
Important Changes Between Versions" ranked by semantic importance — not
chronological order.

## How to Submit

Submission Checklist:
- Public (or private + shared) GitHub repo
- `/samples` folder containing both FDS documents
- Dockerfile that builds and runs everything
- `.env.example` with all keys (no real values!)

README.md must cover:
- Setup instructions — native and Docker
- Architecture overview (chunking, embedding, retrieval)
- Cross-document retrieval strategy
- Model & provider choices with rationale
- Known limitations / what you'd improve

Sample Documents:
| Role | File | Notes |
|---|---|---|
| Doc A | FDS_PriceBook_V0.pdf | Baseline — older version |
| Doc B | FDS_PriceBook_V5.docx | Expanded — new sections, updated figures |
