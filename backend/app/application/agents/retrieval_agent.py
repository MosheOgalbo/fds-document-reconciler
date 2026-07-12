"""
Retrieval Agent.

Single responsibility: turn (query, document scope) into a ranked, dedup'd,
token-budgeted set of context chunks. Nothing here writes an answer —
that's the Response Agent's job. Keeping retrieval pure makes it possible
to swap Pinecone for another vector DB without touching generation code.

Pipeline: embed query -> vector search (child chunks) -> rerank ->
expand top hits to their parent chunks -> dedupe overlapping parents ->
trim to token budget.
"""
from __future__ import annotations

import logging

from app.application.agents.state import GraphState
from app.core.config import get_settings
from app.core.tokens import truncate_to_token_budget
from app.infrastructure.ai.openai_client import OpenAIGateway
from app.infrastructure.vectordb.pinecone_client import PineconeVectorStore

logger = logging.getLogger(__name__)


class RetrievalAgent:
    def __init__(self, llm: OpenAIGateway, vector_store: PineconeVectorStore):
        self._llm = llm
        self._store = vector_store
        self._settings = get_settings()

    async def run(self, state: GraphState) -> GraphState:
        query = state["user_query"]
        document_ids = state.get("document_ids") or None

        [query_embedding] = await self._llm.embed([query])

        hits = self._store.query(
            query_embedding=query_embedding,
            top_k=self._settings.retrieval_top_k,
            document_ids=document_ids,
            chunk_type="child",
        )

        reranked = self._rerank(query, hits)[: self._settings.rerank_top_n]

        # Expand each surviving child hit to its parent chunk for full context,
        # deduping by parent_chunk_id so we don't repeat the same parent twice.
        seen_parents: set[str] = set()
        expanded_blocks: list[str] = []
        final_hits: list[dict] = []

        for hit in reranked:
            meta = hit["metadata"]
            parent_id = meta.get("parent_chunk_id") or meta.get("chunk_id")
            if parent_id in seen_parents:
                continue
            seen_parents.add(parent_id)

            parent_meta = (
                self._store.fetch_parent(meta["parent_chunk_id"]) if meta.get("parent_chunk_id") else None
            )
            content = (parent_meta or {}).get("content") or meta.get("content", "")

            block_header = (
                f"[chunk_id: {meta.get('chunk_id')} | {meta.get('document')} ({meta.get('version')}) "
                f"| {meta.get('section')} | page {meta.get('page')}]"
            )
            expanded_blocks.append(f"{block_header}\n{content}")
            final_hits.append(hit)

        expanded_context = self._trim_to_token_budget(
            "\n\n---\n\n".join(expanded_blocks), self._settings.max_context_tokens
        )

        state["retrieved_chunks"] = final_hits
        state["expanded_context"] = expanded_context
        state.setdefault("agent_trace", []).append(f"retrieval_agent:hits={len(final_hits)}")
        return state

    def _rerank(self, query: str, hits: list[dict]) -> list[dict]:
        """
        Rerank stage. Production version would call a dedicated cross-encoder
        reranker (e.g. Cohere Rerank or a local cross-encoder model); here we
        apply a lightweight lexical-overlap boost on top of the vector score
        as a pragmatic stand-in, keeping the interface identical so swapping
        in a real reranker later is a one-line change (see README limitations).
        """
        query_terms = set(query.lower().split())

        def score(hit: dict) -> float:
            content = hit["metadata"].get("content", "").lower()
            overlap = sum(1 for term in query_terms if term in content)
            return hit["score"] + 0.01 * overlap

        return sorted(hits, key=score, reverse=True)

    def _trim_to_token_budget(self, text: str, budget: int) -> str:
        return truncate_to_token_budget(text, budget)
