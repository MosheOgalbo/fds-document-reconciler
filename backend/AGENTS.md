# 🤖 Agents Documentation

## Overview

7 agents in LangGraph workflow orchestrating document reconciliation:

```
Router → Retrieval → [Compare | Chat | Summary]
```

---

## Agent Definitions

### 1. Router Agent

**Role:** Intent classifier. First touch for all queries — fast model tier.

**Input:** `query`, conversation history  
**Output:** `intent` (enum), `document_focus`, `confidence_score`

**Intent Types:**
- `single_document_chat` — questions about one document only
- `cross_document_chat` — comparative questions, or "show me both"
- `compare_documents` — explicit comparison request
- `executive_summary` — "top changes", "summary", "what's new"

**System Prompt Summary:**
```
You are an intent classifier for a document reconciliation system.
Classify the user's query into one of four intents.

RULES:
1. Prefer the most specific intent (e.g., "what changed" → compare_documents, not chat)
2. If query mentions both documents explicitly → cross_document_chat
3. If query asks for "top X", "summary", "what's new" → executive_summary
4. If ambiguous, return confidence_low and let the calling code prompt for clarification

Pattern matching:
- Keywords for compare: "changed", "diff", "difference", "compare", "vs.", "between"
- Keywords for summary: "summary", "top", "important", "highlights", "overview"
- Keywords for single-doc: product name, section name, specific term (not comparative)

Return JSON:
{
  "intent": "single_document_chat" | "cross_document_chat" | "compare_documents" | "executive_summary",
  "document_focus": ["doc_a", "doc_b"] or ["doc_a"] or null,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation of classification"
}
```

**Key Behaviors:**
- Fast model tier (cost-optimized for high-volume first touch)
- Does NOT access vector database
- Conversation memory influences classification (e.g., if prior turns discussed doc_a, default to single_document_chat)

**See:** `backend/app/application/agents/router_agent.py`

---

### 2. Retrieval Agent

**Role:** Dense vector search → rerank → parent expansion → token budgeting.

**Input:** `query`, `document_ids`, `top_k` (default: 20)  
**Output:** `chunks` (ranked list with citations)

**Orchestration:**
1. Query Pinecone with child chunks (`text-embedding-3-large` embedding)
2. Filter by `document_id` ∈ provided list
3. Apply lexical-overlap rerank boost on top of vector similarity
4. Expand child chunks to parent chunks (full section context)
5. Dedup by content hash
6. Truncate to `MAX_CONTEXT_TOKENS` (default: 8000)
7. Return ranked list with `[document | section | page N]` citations

**System Prompt Summary:**
```
You are a retrieval orchestrator. Your job is to:
1. Issue a dense vector query against a Pinecone index
2. Rerank results by relevance (vector similarity + lexical overlap)
3. Expand to parent chunks for context
4. Manage token budget strictly

RULES:
1. Single-doc queries: filter by document_id
2. Cross-doc queries: filter by {"document_id": {"$in": [doc_a, doc_b]}}
   (Single query, NOT dual queries)
3. Dedup identical content across documents
4. If token budget exhausted, drop trailing chunks (don't merge/compress)
5. Return citations in exact format: [document | section | page N]

Token budget is HARD. If you exceed it, truncate and return what fits.
Don't try to be clever with compression.
```

**Reranking Strategy:**
- Primary: vector similarity (from Pinecone)
- Secondary: lexical overlap boost (BM25-style term frequency)
- **Future improvement:** Cross-encoder reranker (Cohere, MixedBread); see DECISIONS.md D-12

**See:** `backend/app/application/agents/retrieval_agent.py`

---

### 3. Comparison Agent

**Role:** Structured 3-category comparison (MATCH / DIFF / MISSING).

**Input:** `query`, `chunks_doc_a`, `chunks_doc_b`  
**Output:** JSON schema with `{missing, diff, match}`

**Output Schema (Strict):**
```json
{
  "missing": [
    {
      "text": "content from one doc, absent from other",
      "source_file": "FDS_PriceBook_V0.pdf",
      "location": "Page 5, Section 3.1 — Phase A Overview"
    }
  ],
  "diff": [
    {
      "docA_text": "content in V0",
      "docB_text": "content in V5",
      "reason": "explanation of what changed and why it matters",
      "sourceA": "FDS_PriceBook_V0.pdf / Page 2, Section 2",
      "sourceB": "FDS_PriceBook_V5.docx / Page 4, Section 2.1"
    }
  ],
  "match": [
    {
      "textA": "identical or semantically equivalent content",
      "textB": "identical or semantically equivalent content",
      "source": "FDS_PriceBook_V0.pdf / Page 12, Section 4.2 + FDS_PriceBook_V5.docx / Page 15, Section 4.2"
    }
  ]
}
```

**System Prompt Summary:**
```
You are a document comparison analyzer. Your job is to categorize differences.

OUTPUT SCHEMA:
1. "match" — content present in both docs, identical or semantically equivalent
2. "diff" — content present in both docs, but meaningfully changed
3. "missing" — content in one doc, absent from the other

CRITICAL RULES:
1. Every item MUST include a source location from the retrieved chunks
2. Location format: "Page N, Section X.Y" or "Section Heading"
3. If you cannot pin a claim to a real chunk location, DROP THE CLAIM
4. Do NOT fabricate file names, page numbers, or section names
5. Be precise: "changed X to Y" is better than "updated"
6. Return valid JSON only; no markdown or extra text

CATEGORIZATION LOGIC:
- "match": exact text match OR semantic equivalence (same meaning, different wording)
- "diff": both docs have it, but the content or emphasis changed
- "missing": one doc has it, other doesn't (could be new feature, removed section, etc.)

Don't invent categories. Stick to match/diff/missing.
```

**Grounding Rule:**
- Every claim is drawn from retrieved chunks
- If a claim can't be grounded, the claim is dropped (not the entire category)
- This is enforced at validation layer, not here — just be honest about what you found

**See:** `backend/app/application/agents/comparison_agent.py`

---

### 4. Response Agent

**Role:** Grounded free-text answer generation with inline citations.

**Input:** `query`, `retrieved_chunks`, `intent`  
**Output:** `answer` (plain text with citations), `citations` (list of chunk references)

**System Prompt Summary:**
```
You are a Q&A assistant for document reconciliation.

RULES:
1. Answer the user's question using ONLY retrieved context
2. Cite every factual claim inline: [citation: chunk_id_N, source: doc/section]
3. For single-document queries: cite only from that document
4. For cross-document queries: distinguish which doc supports which claim
5. If retrieved context is insufficient, say so clearly
6. Answer length: 100–500 words (concise, not exhaustive)

CITATION FORMAT:
[citation: chunk_N, source: "FDS_PriceBook_V0.pdf / Section 3.1"]

If you make a claim that ISN'T supported by retrieved context, you MUST cite it.
If you cannot cite it, DELETE it from the answer.

Retrieved context OUTRANKS conversation memory. If they conflict, use retrieved.
Never speculate or add background knowledge outside the documents.
```

**Key Behaviors:**
- Smart model tier (capable reasoning over retrieved context)
- Cites inline (not footnotes)
- Refuses to answer if context is insufficient (falls back to "insufficient information")

**See:** `backend/app/application/agents/response_agent.py`

---

### 5. Validation Agent

**Role:** Anti-hallucination detection. Two layers: structural + semantic.

**Input:** `draft_answer`, `citations`, `retrieved_chunks`  
**Output:** `ValidationResult` with `is_grounded`, `confidence`, `unsupported_claims`

**Layer 1 — Structural Check (No LLM Call):**
- Verify every cited `chunk_id` exists in retrieved set
- If citation references a chunk not in retrieved context → flag as unsupported
- Instant cost: 0, accuracy: 100%

**Layer 2 — Semantic Check (LLM Call, Smart Tier):**
- For each claim in draft answer: is it entailed by retrieved context?
- Return `is_grounded: true/false`, `confidence: 0.0–1.0`
- List specific unsupported claims

**System Prompt Summary:**
```
You are a grounding validator. Your job is to verify that claims in an answer 
are actually supported by retrieved context.

RULES:
1. Structural check: cite chunk IDs must exist in retrieved set
2. Semantic check: each claim must be ENTAILED by retrieved context
3. Entailment is strict: implicit claims do NOT count as entailed
4. Example:
   - Retrieved: "Phase A delivers live QA"
   - Claim: "Phase A is fast" ← NOT entailed (speed not mentioned)
   - Claim: "Phase A is about validation" ← ENTAILED (same meaning)

5. For cross-document questions:
   - Mixing context from Doc A + Doc B is OK (that's the point of cross-doc queries)
   - But be explicit: "Doc A says X, Doc B says Y"

6. Return JSON:
   {
     "is_grounded": true/false,
     "confidence": 0.7,
     "unsupported_claims": ["claim X", "claim Y"]
   }

If is_grounded=false, the Response Agent will fall back to "insufficient information".
Be strict: better to say "not grounded" than to pass a hallucinated claim.
```

**Fallback Behavior:**
- If either layer flags unsupported claims, API returns `is_grounded: false`
- Response Agent rewrites answer to "I don't have sufficient information to answer that"
- User sees grounding status in response

**See:** `backend/app/application/agents/validation_agent.py`

---

### 6. Comparison (Summary Branch)

**Role:** Extract semantic changes for ranking.

Same as Comparison Agent (Task 3), but output is fed to Summary Agent rather than returned directly.

**See:** `backend/app/application/agents/comparison_agent.py` (reused)

---

### 7. Summary Agent

**Role:** Top-10 ranking of semantic changes by business/workflow impact.

**Input:** `comparison_result` (match/diff/missing), `document_ids`  
**Output:** `{top_important_changes: [{rank, title, description, ranking_rationale, impact_category}]}`

**Output Schema:**
```json
{
  "top_important_changes": [
    {
      "rank": 1,
      "title": "Pricing Automation Phase Delivery Restructure",
      "description": "Three-phase delivery (A/B/C) replaces single batch approach; introduces real-time QA and API-driven pipeline",
      "ranking_rationale": "Fundamental workflow transformation; affects all downstream pricing generation, scheduling, and system integration",
      "impact_category": "business_impact",
      "source_diff_ids": ["diff_chunk_12", "diff_chunk_45"]
    },
    {
      "rank": 2,
      "title": "ACM Generation Automation",
      "description": "Python script refactored to be parameterized; supports multiple currencies without code changes",
      "ranking_rationale": "Unblocks quarterly release cycle; reduces manual intervention from 2 hours to 15 minutes",
      "impact_category": "workflow_impact",
      "source_diff_ids": ["diff_chunk_78"]
    }
    // ... up to 10 items
  ]
}
```

**Ranking Rubric (Priority Order):**

1. **Business Impact** (Rank 1–3)
   - Pricing rule changes, revenue model shifts, cost trade-offs
   - Customer-facing feature changes, support/maintenance model changes
   - Quarterly release cycle impact, customer communication required

2. **Workflow / Architecture** (Rank 4–7)
   - Process redesign, automation scope, tooling changes
   - Integration points (Agile, Oracle), pipeline refactoring
   - Team efficiency gains, manual effort reduction

3. **Scope & Scale** (Rank 8–10)
   - New regions, currencies, product lines, scale constraints
   - Edge cases, configuration options, technical constraints
   - Non-blocking enhancements

**System Prompt Summary:**
```
You are a change ranker. Your job is to identify the TOP 10 most important changes 
between two documents and rank them by SEMANTIC IMPORTANCE (not chronological order).

INPUT: List of diffs (changes) from comparison

OUTPUT SCHEMA:
{
  "top_important_changes": [
    {
      "rank": 1-10,
      "title": "short title",
      "description": "1-2 sentence explanation",
      "ranking_rationale": "WHY this ranks at position N (e.g., 'Blocks release cycle', 'Affects all customers')",
      "impact_category": "business_impact" | "workflow_impact" | "scope_scale",
      "source_diff_ids": ["diff_123", "diff_456"]
    }
  ]
}

RANKING LOGIC:
- Rank by IMPACT, not by document position or word count
- Business impact (pricing, revenue, customers) → Rank 1–3
- Workflow impact (process, automation, tooling) → Rank 4–7
- Scope/scale (regions, configs, constraints) → Rank 8–10

RULES:
1. Return exactly 10 items, or fewer if there are fewer unique changes
2. Each rank must be unique (no ties)
3. Don't rank by chronology ("Phase A comes before Phase B, so rank higher")
4. Don't rank by length ("longer diffs are more important")
5. Be explicit in ranking_rationale (e.g., "Affects Q3 release timeline" > "Important change")
6. If you're unsure between ranks 5 and 6, pick one and explain in rationale

DEFENSIVE RE-SORT:
The server will re-sort your output by rank field after you return it.
Don't trust your own output order — the rank field is the source of truth.
```

**Key Behaviors:**
- Smart model tier (nuanced reasoning about business impact)
- Defensive re-sort on server side (ensures rank order is correct)
- If <10 unique changes exist, return fewer (don't pad)

**See:** `backend/app/application/agents/summary_agent.py`

---

### 8. Citation Agent

**Role:** Dedup and format citations in final response.

**Input:** `answer`, `citations`, `retrieved_chunks`  
**Output:** `formatted_answer` with clean citations

**Orchestration:**
1. Extract all citations from response
2. Verify each `chunk_id` exists in retrieved set
3. Remove duplicates (same content, different chunk_id)
4. Reformat citations to: `[doc | section | page N]`
5. Return answer with verified citations

**System Prompt:** None — purely deterministic logic, no LLM call needed.

**See:** `backend/app/application/agents/citation_agent.py`

---

## Workflow Diagram

```
User Query
    ↓
Router Agent (fast model)
    ↓ classifies intent
    ↓
┌───────────────────────────────────┐
│ Route based on intent:            │
├───────────────────────────────────┤
│ → compare_documents               │
│   ↓                               │
│   Retrieval Agent                 │
│   ↓                               │
│   Comparison Agent (smart)        │
│   ↓                               │
│   Comparison Result               │
│                                   │
│ → executive_summary               │
│   ↓                               │
│   Retrieval Agent                 │
│   ↓                               │
│   Comparison Agent (smart)        │
│   ↓                               │
│   Summary Agent (smart)           │
│   ↓                               │
│   Top-10 Ranked Result            │
│                                   │
│ → single_document_chat            │
│ → cross_document_chat             │
│   ↓                               │
│   Retrieval Agent                 │
│   ↓                               │
│   Response Agent (smart)          │
│   ↓                               │
│   Validation Agent (smart)        │
│   ↓ is_grounded?                  │
│   ├─ yes → Citation Agent         │
│   │         ↓                     │
│   │         Formatted Answer      │
│   └─ no → "Insufficient Info"     │
└───────────────────────────────────┘
```

---

## Environment & Configuration

See `backend/.env.example` for:
- `OPENAI_FAST_MODEL` (Router, Summarization)
- `OPENAI_SMART_MODEL` (Comparison, Response, Validation, Summary)
- `RETRIEVAL_TOP_K` (default: 20, dense search breadth)
- `RERANK_TOP_N` (default: 10, reranked results)
- `MAX_CONTEXT_TOKENS` (default: 8000, token budget for retrieved chunks)

---

## Testing

- `tests/unit/` — agent logic in isolation (no API calls)
- `tests/integration/` — full LangGraph workflows via fakes
- `tests/api/` — FastAPI endpoints + error handling
- `pytest -v` to run all

See individual test files for expected inputs/outputs per agent.
