"""
Domain entities for FDS documents.

These are pure business objects with zero dependency on FastAPI, Pinecone,
OpenAI, or any infrastructure concern. This is what makes the domain layer
testable in isolation and swappable at the infrastructure boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ChunkType(str, Enum):
    PARENT = "parent"
    CHILD = "child"


@dataclass
class MissingItem:
    """One row of the 'missing' category: content present in one document,
    absent from the other. Exact field names match the required output schema."""
    text: str
    source_file: str
    location: str  # e.g. "Page 12, Section 3.1"


@dataclass
class DiffItem:
    """One row of the 'diff' category: same topic, meaningfully changed content."""
    docA_text: str
    docB_text: str
    reason: str
    sourceA: str
    sourceB: str
    semantic_similarity: Optional[float] = None  # cosine similarity 0-1 when available


@dataclass
class MatchItem:
    """One row of the 'match' category: semantically equivalent content in both docs."""
    textA: str
    textB: str
    source: str  # e.g. "docA.pdf / Page 2 + docB.docx / Page 2"
    similarity_score: Optional[float] = None  # cosine similarity 0-1 when available


@dataclass
class ComparisonReport:
    """
    The full Document Comparison Engine output. Serializes to the assignment
    JSON structure, with optional numeric similarity fields when enrichment ran:

        {
          "missing": [{ "text", "source_file", "location" }],
          "diff":    [{ "docA_text", "docB_text", "reason", "sourceA", "sourceB",
                        "semantic_similarity"? }],
          "match":   [{ "textA", "textB", "source", "similarity_score"? }]
        }
    """
    missing: list[MissingItem] = field(default_factory=list)
    diff: list[DiffItem] = field(default_factory=list)
    match: list[MatchItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "missing": [m.__dict__.copy() for m in self.missing],
            "diff": [_optional_fields(d.__dict__) for d in self.diff],
            "match": [_optional_fields(m.__dict__) for m in self.match],
        }


def _optional_fields(row: dict) -> dict:
    """Omit None optional scores so the core brief schema stays clean when unset."""
    return {k: v for k, v in row.items() if v is not None}


@dataclass(frozen=True)
class SectionPath:
    """
    Represents where a piece of content lives in the document hierarchy.
    Preserved through ingestion so citations can point to an exact
    section/page rather than just 'somewhere in the document'.
    """
    heading_trail: tuple[str, ...]  # e.g. ("3. Pricing", "3.2 Discounts")
    page_number: int

    def as_breadcrumb(self) -> str:
        return " > ".join(self.heading_trail) if self.heading_trail else "Document Root"


@dataclass
class DocumentChunk:
    """
    A single retrievable unit. Child chunks are small and precise for
    embedding similarity; parent chunks carry surrounding context that
    gets injected at generation time (parent-child retrieval pattern).
    """
    chunk_id: str
    document_id: str
    document_name: str
    version: str
    content: str
    section: SectionPath
    chunk_type: ChunkType
    parent_chunk_id: Optional[str] = None
    token_count: int = 0
    embedding: Optional[list[float]] = None
    chunk_index: int = 0
    char_offset: int = 0

    def to_metadata(self) -> dict:
        """Metadata payload stored alongside the vector in Pinecone."""
        heading_trail = self.section.heading_trail
        return {
            "document": self.document_name,
            "document_id": self.document_id,
            "version": self.version,
            "page": self.section.page_number,
            "section": self.section.as_breadcrumb(),
            "heading": heading_trail[-1] if heading_trail else "",
            "section_heading": heading_trail[0] if heading_trail else "",
            "subsection_heading": heading_trail[-1] if len(heading_trail) > 1 else (
                heading_trail[0] if heading_trail else ""
            ),
            "chunk_id": self.chunk_id,
            "chunk_type": self.chunk_type.value,
            "chunk_index": self.chunk_index,
            "char_offset": self.char_offset,
            "parent_chunk_id": self.parent_chunk_id or "",
            "filename": self.document_name,
        }


@dataclass
class Citation:
    """A grounding pointer from a claim back to source material. Every
    factual statement the system produces must be traceable to one of these."""
    document_name: str
    version: str
    page_number: int
    section: str
    chunk_id: str
    confidence: float
    quoted_snippet: str = ""


@dataclass
class GroundedAnswer:
    """
    The final answer returned to the user. `is_grounded=False` means the
    Validation Agent could not tie every claim to a citation and the
    Response Agent must fall back to an 'insufficient information' answer
    rather than let anything ungrounded through.
    """
    answer_text: str
    citations: list[Citation]
    is_grounded: bool
    confidence: float
    warnings: list[str] = field(default_factory=list)
