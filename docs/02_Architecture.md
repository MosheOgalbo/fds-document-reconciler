# Architecture

## Alternatives considered

### 1. Clean Architecture (chosen)

Concentric layers — Domain → Application → Infrastructure → Presentation —
dependencies point inward only; outer layers depend on inner ones, never
the reverse.

**Advantages**
- Domain entities (`DocumentChunk`, `Citation`, `ComparisonReport`) have zero
  dependency on FastAPI/Pinecone/OpenAI — trivially unit-testable.
- Swapping infrastructure (e.g. Pinecone → Qdrant) touches one file
  (`infrastructure/vectordb/`), never the agents or domain.
- Maps naturally onto a LangGraph agent pipeline: each agent is an
  Application-layer orchestrator that calls Infrastructure through a
  narrow interface (`OpenAIGateway`, `PineconeVectorStore`).

**Disadvantages**
- More directories/indirection than a flat script for a ~4-hour take-home.
- Requires discipline to keep business logic out of controllers — easy to
  violate under time pressure.

### 2. Hexagonal Architecture (Ports & Adapters)

Conceptually very close to Clean Architecture — the core defines "ports"
(interfaces), and "adapters" implement them for specific tech (Pinecone
adapter, OpenAI adapter).

**Advantages:** same testability benefits as Clean Architecture; arguably
clearer naming for the port/adapter boundary itself.
**Disadvantages:** for a project this size, the distinction from Clean
Architecture is mostly vocabulary — adopting it wouldn't change a single
actual file in this codebase, so it wasn't worth the naming migration.

### 3. Modular Monolith (feature-sliced)

Organize by feature/vertical slice (`features/comparison/`,
`features/chat/`, `features/summary/`) each containing its own
models/services/routes, rather than horizontal layers.

**Advantages:** very fast to navigate for a small number of well-isolated
features; less cross-layer ceremony.
**Disadvantages:** the four features here (comparison, single-doc chat,
cross-doc chat, summary) **share almost their entire pipeline** — parsing,
chunking, retrieval, the same LangGraph — so slicing by feature would mean
either duplicating that shared pipeline per feature or immediately
reintroducing a shared-layer structure anyway (i.e. converging back to
Clean Architecture, just with extra steps).

## Decision

**Clean Architecture**, because the four required capabilities are variations
on one shared retrieval+generation pipeline, not independent verticals —
that shared-core shape is exactly what layered architecture is for. See
`DECISIONS.md` D-01 for the full rationale record.

## Layers in this codebase

```
Presentation  (FastAPI routes, middleware)          — no business logic
    v
Application   (LangGraph agents, use cases, DTOs)   — orchestration
    v
Domain        (entities, exceptions)                — pure, dependency-free
    ^
Infrastructure (OpenAI, Pinecone, parsers, security) — implements the
                                                        interfaces Application uses
```

Rule enforced throughout: infrastructure classes (`OpenAIGateway`,
`PineconeVectorStore`) are constructed and injected into agents/use cases at
the composition root (`graph.py`, `query_documents.py`) — agents depend on
these concrete classes' *public methods* as their de-facto interface (a
lightweight, pragmatic form of dependency injection appropriate for this
scale; a formal `Protocol`/ABC layer would be the next step at larger scale
— see `DECISIONS.md` D-07).
