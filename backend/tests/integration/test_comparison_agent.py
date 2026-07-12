"""
Edge case test for comparison agent when both documents are identical.

This test belongs in: backend/tests/integration/test_comparison_agent.py

Add this test function to the existing test file.
"""

import pytest
from backend.app.domain.entities.document import DocumentChunk, SectionPath, ChunkType
from backend.app.application.agents.comparison_agent import ComparisonAgent
from backend.app.infrastructure.ai.openai_client import OpenAIClient


@pytest.mark.asyncio
async def test_comparison_identical_documents():
    """
    Edge case: Both documents contain identical content.
    
    Expectation:
    - comparison.match: populated with all sections/content
    - comparison.diff: empty (no differences)
    - comparison.missing: empty (no missing content)
    - is_grounded: True (all claims are supported)
    """
    # Mock chunks representing identical content from both documents
    identical_chunks_a = [
        DocumentChunk(
            chunk_id="chunk_1_v0",
            document_id="doc_a",
            document_name="FDS_PriceBook_V0.pdf",
            version="v0",
            content="Phase A delivers real-time QA on PB Draft with live field validation.",
            section=SectionPath(heading_trail=("Phase A - Live QA on PB Draft",), page_number=4),
            chunk_type=ChunkType.CHILD
        ),
        DocumentChunk(
            chunk_id="chunk_2_v0",
            document_id="doc_a",
            document_name="FDS_PriceBook_V0.pdf",
            version="v0",
            content="Phase B retains the current process structure but replaces human coordination with automated execution.",
            section=SectionPath(heading_trail=("Phase B - Automating the Existing Process",), page_number=5),
            chunk_type=ChunkType.CHILD
        ),
    ]
    
    identical_chunks_b = [
        DocumentChunk(
            chunk_id="chunk_1_v5",
            document_id="doc_b",
            document_name="FDS_PriceBook_V5.docx",
            version="v5",
            content="Phase A delivers real-time QA on PB Draft with live field validation.",
            section=SectionPath(heading_trail=("Phase A - Live QA on PB Draft",), page_number=4),
            chunk_type=ChunkType.CHILD
        ),
        DocumentChunk(
            chunk_id="chunk_2_v5",
            document_id="doc_b",
            document_name="FDS_PriceBook_V5.docx",
            version="v5",
            content="Phase B retains the current process structure but replaces human coordination with automated execution.",
            section=SectionPath(heading_trail=("Phase B - Automating the Existing Process",), page_number=5),
            chunk_type=ChunkType.CHILD
        ),
    ]
    
    # Initialize comparison agent with mock OpenAI client
    openai_client = OpenAIClient()
    comparison_agent = ComparisonAgent(openai_client=openai_client)
    
    # Run comparison
    result = await comparison_agent.compare(
        query="Compare the two versions",
        chunks_doc_a=identical_chunks_a,
        chunks_doc_b=identical_chunks_b
    )
    
    # Assertions
    assert result is not None, "Comparison result should not be None"
    assert result.is_grounded is True, "Result should be grounded (claims supported by retrieved chunks)"
    
    # When docs are identical, all content should be in "match" category
    assert len(result.match) > 0, "Should have matched content when documents are identical"
    assert len(result.diff) == 0, "Should have no diffs when documents are identical"
    assert len(result.missing) == 0, "Should have no missing content when documents are identical"
    
    # Verify citations for matched content
    for match_item in result.match:
        assert match_item.source, "Each match should include source citation"
        assert "FDS_PriceBook_V0.pdf" in match_item.source or "FDS_PriceBook_V5.docx" in match_item.source
        assert match_item.textA == match_item.textB, "Matched text should be identical"


@pytest.mark.asyncio
async def test_comparison_empty_documents():
    """
    Edge case: One or both documents are empty.
    
    Expectation:
    - All empty sections are reported in missing
    - No crashes, graceful handling
    """
    empty_chunks = []
    normal_chunks = [
        DocumentChunk(
            chunk_id="chunk_1",
            document_id="doc_a",
            document_name="FDS_PriceBook_V0.pdf",
            version="v0",
            content="Some content",
            section=SectionPath(heading_trail=("Section 1",), page_number=1),
            chunk_type=ChunkType.CHILD
        )
    ]
    
    openai_client = OpenAIClient()
    comparison_agent = ComparisonAgent(openai_client=openai_client)
    
    # Compare empty vs. normal
    result = await comparison_agent.compare(
        query="Compare empty and normal documents",
        chunks_doc_a=empty_chunks,
        chunks_doc_b=normal_chunks
    )
    
    # Should gracefully handle the empty case
    assert result is not None
    assert len(result.missing) > 0, "Should report missing content from empty doc"
    # Empty doc has nothing, so nothing in match or diff
    assert len(result.match) == 0


@pytest.mark.asyncio
async def test_comparison_partial_diff():
    """
    Edge case: Some content matches, some differs, some is missing.
    Realistic scenario with mixed changes.
    
    Expectation:
    - match: unchanged sections
    - diff: changed sections  
    - missing: added/removed sections
    - All categories populated
    """
    chunks_v0 = [
        DocumentChunk(
            chunk_id="chunk_1_v0",
            document_id="doc_a",
            document_name="FDS_PriceBook_V0.pdf",
            version="v0",
            content="Phase A delivers real-time QA.",
            section=SectionPath(heading_trail=("Phase A",), page_number=4),
            chunk_type=ChunkType.CHILD
        ),
        DocumentChunk(
            chunk_id="chunk_2_v0",
            document_id="doc_a",
            document_name="FDS_PriceBook_V0.pdf",
            version="v0",
            content="Phase B automates existing steps.",
            section=SectionPath(heading_trail=("Phase B",), page_number=5),
            chunk_type=ChunkType.CHILD
        ),
    ]
    
    chunks_v5 = [
        DocumentChunk(
            chunk_id="chunk_1_v5",
            document_id="doc_b",
            document_name="FDS_PriceBook_V5.docx",
            version="v5",
            content="Phase A delivers real-time QA with live field validation.",  # DIFF: added validation detail
            section=SectionPath(heading_trail=("Phase A",), page_number=4),
            chunk_type=ChunkType.CHILD
        ),
        DocumentChunk(
            chunk_id="chunk_2_v5",
            document_id="doc_b",
            document_name="FDS_PriceBook_V5.docx",
            version="v5",
            content="Phase B automates existing steps.",  # MATCH: unchanged
            section=SectionPath(heading_trail=("Phase B",), page_number=5),
            chunk_type=ChunkType.CHILD
        ),
        DocumentChunk(
            chunk_id="chunk_3_v5",
            document_id="doc_b",
            document_name="FDS_PriceBook_V5.docx",
            version="v5",
            content="Phase C transforms beyond Excel to modern platform.",  # MISSING: not in V0
            section=SectionPath(heading_trail=("Phase C - Transformation",), page_number=6),
            chunk_type=ChunkType.CHILD
        ),
    ]
    
    openai_client = OpenAIClient()
    comparison_agent = ComparisonAgent(openai_client=openai_client)
    
    result = await comparison_agent.compare(
        query="Compare versions",
        chunks_doc_a=chunks_v0,
        chunks_doc_b=chunks_v5
    )
    
    # All three categories should be populated
    assert len(result.match) > 0, "Should have matched sections"
    assert len(result.diff) > 0, "Should have changed sections"
    assert len(result.missing) > 0, "Should have missing sections"
    
    # Verify citations are present and valid
    for diff_item in result.diff:
        assert diff_item.sourceA, "Diff should cite source from doc A"
        assert diff_item.sourceB, "Diff should cite source from doc B"
        assert diff_item.reason, "Diff should explain what changed"


if __name__ == "__main__":
    # Run with: pytest backend/tests/integration/test_comparison_agent.py::test_comparison_identical_documents -v
    pytest.main([__file__, "-v"])
