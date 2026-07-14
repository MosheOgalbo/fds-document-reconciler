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
from app.infrastructure.ai.llm_gateway import LLMGateway
from app.infrastructure.vectordb.pinecone_client import PineconeVectorStore

logger = logging.getLogger(__name__)

_COMPARE_FOCUS_QUERY = (
    "Compare all sections, rules, requirements, phases, pricing, workflows, "
    "and functional specifications between both document versions."
)


class RetrievalAgent:
    def __init__(self, llm: LLMGateway, vector_store: PineconeVectorStore):
        self._llm = llm
        self._store = vector_store
        self._settings = get_settings()

    async def run(self, state: GraphState) -> GraphState:
        query = state["user_query"]
        document_ids = state.get("document_ids") or None
        intent = state.get("intent", "")
        is_compare = intent in ("compare_documents", "executive_summary")

        try:
            [query_embedding] = await self._llm.embed([query])
            if is_compare and document_ids and len(document_ids) >= 2:
                hits = self._compare_balanced_retrieval(query, query_embedding, document_ids)
            else:
                hits = self._store.query(
                    query_embedding=query_embedding,
                    top_k=self._settings.retrieval_top_k,
                    document_ids=document_ids,
                    chunk_type="child",
                )
        except Exception as e:
            logger.warning("Embedding failed; falling back to lexical retrieval: %s", e)
            hits = self._store.lexical_query(
                query=query,
                top_k=self._settings.retrieval_top_k,
                document_ids=document_ids,
                chunk_type="child",
            )

        if not is_compare and document_ids and len(document_ids) == 2:
            present = {h.get("metadata", {}).get("document_id") for h in hits}
            missing_docs = [d for d in document_ids if d not in present]
            for missing_doc_id in missing_docs:
                extra = self._store.lexical_query(
                    query=query,
                    top_k=max(6, self._settings.rerank_top_n),
                    document_ids=[missing_doc_id],
                    chunk_type="child",
                )
                hits.extend(extra)

        rerank_limit = (
            self._settings.compare_rerank_top_n
            if is_compare
            else self._settings.rerank_top_n
        )
        reranked = self._rerank(query, hits)[:rerank_limit]

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
        state.setdefault("agent_trace", []).append(
            f"retrieval_agent:hits={len(final_hits)}{',mode=compare' if is_compare else ''}"
        )
        return state

    def _compare_balanced_retrieval(
        self,
        query: str,
        query_embedding: list[float],
        document_ids: list[str],
    ) -> list[dict]:
        """Retrieve a balanced slice from each document for fair comparison."""
        focus_query = query.strip() or _COMPARE_FOCUS_QUERY
        per_doc_k = max(self._settings.retrieval_top_k // 2, 12)
        hits: list[dict] = []
        seen_ids: set[str] = set()

        for doc_id in document_ids[:2]:
            doc_hits = self._store.query(
                query_embedding=query_embedding,
                top_k=per_doc_k,
                document_ids=[doc_id],
                chunk_type="child",
            )
            for hit in doc_hits:
                cid = str(hit.get("chunk_id") or "")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    hits.append(hit)

            lexical_hits = self._store.lexical_query(
                query=focus_query,
                top_k=8,
                document_ids=[doc_id],
                chunk_type="child",
            )
            for hit in lexical_hits:
                cid = str(hit.get("chunk_id") or "")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    hits.append(hit)

        return self._balance_by_document(hits, document_ids[:2], self._settings.compare_rerank_top_n)

    def _balance_by_document(
        self,
        hits: list[dict],
        document_ids: list[str],
        limit: int,
    ) -> list[dict]:
        by_doc: dict[str, list[dict]] = {doc_id: [] for doc_id in document_ids}
        for hit in hits:
            doc_id = str(hit.get("metadata", {}).get("document_id") or "")
            if doc_id in by_doc:
                by_doc[doc_id].append(hit)

        per_doc_quota = max(limit // max(len(document_ids), 1), 4)
        balanced: list[dict] = []
        seen: set[str] = set()

        for doc_id in document_ids:
            for hit in by_doc.get(doc_id, [])[:per_doc_quota]:
                cid = str(hit.get("chunk_id") or "")
                if cid and cid not in seen:
                    seen.add(cid)
                    balanced.append(hit)

        for hit in hits:
            if len(balanced) >= limit:
                break
            cid = str(hit.get("chunk_id") or "")
            if cid and cid not in seen:
                seen.add(cid)
                balanced.append(hit)

        return balanced[:limit]

    def _rerank(self, query: str, hits: list[dict]) -> list[dict]:
        if not hits:
            return []

        query_terms = set(query.lower().split())

        def calculate_score(hit: dict) -> float:
            content = hit["metadata"].get("content", "").lower()
            chunk_terms = set(content.split())
            overlap = len(query_terms & chunk_terms) / max(len(query_terms), 1)
            return (0.7 * hit["score"]) + (0.3 * overlap)

        return sorted(hits, key=calculate_score, reverse=True)

    def _trim_to_token_budget(self, text: str, budget: int) -> str:
        return truncate_to_token_budget(text, budget)
