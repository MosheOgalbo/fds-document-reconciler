# System Architecture Diagrams

## High-Level Diagram

```mermaid
flowchart LR
    User[Product Manager] --> API[FastAPI]
    API --> Graph[LangGraph Multi-Agent Workflow]
    Graph --> OpenAI[OpenAI: fast + smart models, embeddings]
    Graph --> Pinecone[(Pinecone: single index, metadata-partitioned)]
    API --> Memory[(Conversation Memory Store)]
    Ingest[Ingestion Pipeline] --> Pinecone
    PDF[/PDF via pdfplumber/] --> Ingest
    DOCX[/DOCX via python-docx/] --> Ingest
```

## Component Diagram

```mermaid
flowchart TB
    subgraph Presentation
        QR[query_routes.py]
        IR[ingest_routes.py]
        MW[rate_limit + observability middleware]
    end
    subgraph Application
        UC1[QueryDocuments use case]
        UC2[IngestDocument use case]
        subgraph Agents
            Router --> Retrieval
            Retrieval --> Comparison
            Retrieval --> Response
            Comparison --> Summary
            Response --> Validation --> Citation
        end
    end
    subgraph Domain
        Entities[DocumentChunk, Citation, ComparisonReport]
        Errors[DomainError hierarchy]
    end
    subgraph Infrastructure
        OAI[OpenAIGateway]
        PC[PineconeVectorStore]
        Parsers[PDF/DOCX parsers + chunker]
        Mem[ConversationMemoryStore]
        Sec[prompt_injection screening]
    end

    QR --> UC1 --> Agents
    IR --> UC2 --> Parsers
    Agents --> OAI
    Agents --> PC
    UC1 --> Mem
    Agents --> Entities
    UC2 --> PC
```

## Sequence Diagram — Cross-Document Chat

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant R as Router Agent (fast model)
    participant Rt as Retrieval Agent
    participant P as Pinecone
    participant Rs as Response Agent (smart model)
    participant V as Validation Agent (smart model)
    participant C as Citation Agent

    U->>API: POST /api/v1/query {query, document_ids: [A, B]}
    API->>R: classify intent
    R-->>API: intent = cross_doc_chat
    API->>Rt: retrieve(query, document_ids=[A,B])
    Rt->>P: vector search filtered by document_id IN [A,B]
    P-->>Rt: top-k child chunks (both docs)
    Rt->>P: fetch parent chunks for expansion
    Rt-->>API: expanded_context (both docs, deduped, token-budgeted)
    API->>Rs: generate grounded answer
    Rs-->>API: draft_answer + draft_citations
    API->>V: verify grounding
    V-->>API: is_grounded, confidence, warnings
    API->>C: dedupe/verify citations
    C-->>API: final_citations
    API-->>U: answer + citations from both documents
```

## Agent Flow

```mermaid
flowchart TD
    Start([Query received]) --> Router{Router Agent<br/>fast model}
    Router -->|single/cross doc chat| Retrieval1[Retrieval Agent]
    Router -->|compare_documents| Retrieval2[Retrieval Agent]
    Router -->|executive_summary| Retrieval3[Retrieval Agent]

    Retrieval1 --> Response[Response Agent<br/>smart model]
    Response --> Validation[Validation Agent<br/>smart model]
    Validation --> Citation1[Citation Agent]
    Citation1 --> End1([answer + citations])

    Retrieval2 --> Comparison1[Comparison Agent<br/>smart model]
    Comparison1 --> End2([missing / diff / match])

    Retrieval3 --> Comparison2[Comparison Agent<br/>smart model]
    Comparison2 --> Summary[Summary Agent<br/>smart model]
    Summary --> End3([Top-10 ranked changes])
```

## Retrieval Flow (Parent-Child + Dual-Document)

```mermaid
flowchart LR
    Q[User query] --> E[Embed query<br/>text-embedding-3-large]
    E --> S["Pinecone query<br/>filter: chunk_type=child<br/>AND document_id IN [...]"]
    S --> Rerank[Lexical-overlap rerank boost]
    Rerank --> TopN[Top N hits]
    TopN --> Expand[Fetch each hit's parent chunk by ID]
    Expand --> Dedup[Dedupe by parent_chunk_id]
    Dedup --> Budget[Trim to MAX_CONTEXT_TOKENS]
    Budget --> Out[expanded_context]
```

## Document Ingestion Flow

```mermaid
flowchart TD
    F[/PDF or DOCX file/] --> Parse{File type}
    Parse -->|.pdf| PDFP[pdfplumber: extract_text + extract_tables per page]
    Parse -->|.docx| DOCXP[python-docx: iterate body in document order,<br/>convert w:tbl to Markdown]
    PDFP --> Merge[Interleave table Markdown into page text]
    DOCXP --> Merge
    Merge --> Chunk[Hierarchical chunker:<br/>heading-stack tracking + heuristic filter]
    Chunk --> PC[Parent chunks ~1600 tok]
    Chunk --> CC[Child chunks ~400 tok, overlapping]
    PC --> Embed1[Embed]
    CC --> Embed2[Embed]
    Embed1 --> Upsert[(Pinecone upsert<br/>with full metadata)]
    Embed2 --> Upsert
```

## Comparison Flow

```mermaid
flowchart LR
    Ctx[expanded_context: Doc A + Doc B retrieved chunks] --> LLM[Smart model,<br/>structured output json_schema strict]
    LLM --> M[match: textA, textB, source]
    LLM --> D[diff: docA_text, docB_text, reason, sourceA, sourceB]
    LLM --> Miss[missing: text, source_file, location]
    M --> Report[ComparisonReport.to_dict]
    D --> Report
    Miss --> Report
    Report --> JSON["{ missing: [...], diff: [...], match: [...] }"]
```

## Memory Flow

```mermaid
flowchart LR
    Turn[New chat turn] --> Store[ConversationMemoryStore.add_turn]
    Store --> Check{turns > trigger threshold?}
    Check -->|no| Keep[Keep verbatim in session.turns]
    Check -->|yes| Compress[Fast-model summarization of overflow turns]
    Compress --> RunningSummary[session.summary updated]
    RunningSummary --> Inject[Injected into next prompt as background only]
    Keep --> Inject
    Inject --> Rule[["Retrieved document knowledge always outranks<br/>conversation memory on conflict — enforced in every<br/>agent's system prompt, never merged into one blob"]]
```

## Context Flow

```mermaid
flowchart TD
    Hits[Reranked vector hits] --> Parents[Expand to parent chunks]
    Parents --> DedupP[Dedupe by parent_chunk_id]
    DedupP --> Concat[Concatenate with source headers]
    Concat --> TokenCheck{approx tokens > MAX_CONTEXT_TOKENS?}
    TokenCheck -->|no| Final[expanded_context]
    TokenCheck -->|yes| Trim[Truncate + append truncation notice]
    Trim --> Final
```

## Validation Flow

```mermaid
flowchart TD
    Draft[draft_answer + draft_citations] --> Structural{Structural check:<br/>every citation.chunk_id in<br/>retrieved_chunks?}
    Structural -->|no| Fabricated[Flag fabricated citations,<br/>cap confidence <= 0.3]
    Structural -->|yes| Judge[LLM-judge semantic check:<br/>smart model, structured output]
    Fabricated --> Judge
    Judge --> Result{is_grounded AND<br/>no fabricated citations?}
    Result -->|true| Pass[is_grounded = true]
    Result -->|false| Fail["is_grounded = false<br/>Response falls back to<br/>'insufficient information'"]
```
