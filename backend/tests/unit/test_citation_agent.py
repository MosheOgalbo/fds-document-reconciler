import pytest

from app.application.agents.citation_agent import CitationAgent
from app.domain.entities.document import Citation


@pytest.mark.asyncio
async def test_drops_citations_not_in_retrieved_chunks():
    agent = CitationAgent()
    state = {
        "retrieved_chunks": [{"chunk_id": "real-1"}, {"chunk_id": "real-2"}],
        "draft_citations": [
            Citation("Doc.pdf", "v1", 1, "Sec 1", "real-1", 0.9),
            Citation("Doc.pdf", "v1", 2, "Sec 2", "fabricated-99", 0.9),
        ],
    }
    result = await agent.run(state)
    ids = [c.chunk_id for c in result["final_citations"]]
    assert ids == ["real-1"]


@pytest.mark.asyncio
async def test_dedupes_same_section_citation():
    agent = CitationAgent()
    state = {
        "retrieved_chunks": [{"chunk_id": "real-1"}, {"chunk_id": "real-2"}],
        "draft_citations": [
            Citation("Doc.pdf", "v1", 1, "Sec 1", "real-1", 0.9),
            Citation("Doc.pdf", "v1", 1, "Sec 1", "real-2", 0.8),
        ],
    }
    result = await agent.run(state)
    assert len(result["final_citations"]) == 1
