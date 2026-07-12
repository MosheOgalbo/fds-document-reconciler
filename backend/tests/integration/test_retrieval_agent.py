"""
Integration test using fakes instead of real OpenAI/Pinecone calls, so the
suite runs in CI without API keys. Verifies the retrieval agent's contract
(state in -> state out) rather than embedding/vector-search quality, which
belongs in a separate RAG-evaluation suite (see README 'Known limitations'
for what a full eval harness would add: recall@k, groundedness scoring on
a labeled Q&A set, etc.).
"""
import pytest

from app.application.agents.retrieval_agent import RetrievalAgent


class FakeLLM:
    async def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeStore:
    def query(self, query_embedding, top_k, document_ids=None, chunk_type="child"):
        return [
            {
                "chunk_id": "child-1",
                "score": 0.9,
                "metadata": {
                    "document": "Spec.pdf",
                    "version": "v1",
                    "section": "3.2 Discounts",
                    "page": 14,
                    "parent_chunk_id": "parent-1",
                    "content": "Discounts apply above $500 order value.",
                },
            }
        ]

    def fetch_parent(self, parent_chunk_id):
        assert parent_chunk_id == "parent-1"  # verifies the REAL parent_chunk_id was used, not a stray field
        return {"content": "Full parent section text about discount rules."}


@pytest.mark.asyncio
async def test_retrieval_agent_expands_parent_context():
    agent = RetrievalAgent(FakeLLM(), FakeStore())
    state = {"user_query": "What are the discount rules?", "document_ids": ["doc-1"]}

    result = await agent.run(state)

    assert result["retrieved_chunks"]
    # Must contain the PARENT's full text, not just the short child snippet —
    # this is the whole point of parent-child expansion. This assertion
    # would NOT have caught the original bug (it also passes if the code
    # falls back to child content) — the FakeStore.fetch_parent assertion
    # above is what actually pins down correct behavior.
    assert "discount" in result["expanded_context"].lower()
    assert "full parent section" in result["expanded_context"].lower()
    assert any("retrieval_agent" in t for t in result["agent_trace"])
