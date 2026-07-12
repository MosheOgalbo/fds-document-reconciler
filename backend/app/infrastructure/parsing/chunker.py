"""
Hierarchical, structure-aware chunking.

Why not naive fixed-size splitting: a Functional Design Spec is organized as
nested sections (1 > 1.2 > 1.2.3). If we split purely by character count we
lose the ability to say "this came from section 3.2 Pricing, page 14" and
the whole citation/traceability requirement collapses. So chunking here is
driven by the document's own heading structure first, and token-size second.

Strategy: Parent-Child chunking.
  - PARENT chunks: whole section (up to ~1600 tokens) -> stored as context,
    given to the LLM at generation time so it sees full surrounding meaning.
  - CHILD chunks: ~400 token slices of a parent, with overlap -> these are
    what actually gets embedded and matched against the query, because
    small precise chunks embed far better than long ones (less topic
    dilution in the vector).
Both are written to Pinecone; child metadata references parent_chunk_id so
retrieval can "expand" a hit back to its parent for generation.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from app.core.tokens import count_tokens
from app.domain.entities.document import ChunkType, DocumentChunk, SectionPath

_HEADING_PATTERN = re.compile(
    r"^(?P<marker>\d+(?:\.\d+)*)\.?\s+(?P<title>\S.*)$"
)

_MAX_HEADING_LINE_LENGTH = 80


def _looks_like_real_heading(title: str, full_line: str) -> bool:
    """
    The numeric-prefix regex alone is too permissive: real-world PDF text
    extraction produces line-wrapped body text where a line can legitimately
    start with a bare number (e.g. a wrapped sentence "15 manual validation
    rules are executed before the file can be handed off." gets split so
    "15 manual validation..." becomes its own line) or a numbered table row
    ("1  PM PB (Q2-26v1)  PM PB Q2-26v0  Final PM input..."). Verified
    against the actual sample PDF — both cases occur and would otherwise
    corrupt the section hierarchy.

    Two cheap heuristics catch the overwhelming majority of these without
    needing font-size/layout metadata (which plain text extraction doesn't
    expose): real headings are short, and their title text starts with a
    capital letter (mid-sentence wrapped fragments start lowercase).
    """
    if len(full_line) > _MAX_HEADING_LINE_LENGTH:
        return False
    if not title[:1].isupper():
        return False
    return True


@dataclass
class RawPage:
    page_number: int
    text: str


def _approx_token_count(text: str) -> int:
    # Used for the stored per-chunk metadata field — called once per chunk
    # (low frequency), so the accurate tiktoken-backed counter is worth it
    # here. (The word-by-word splitting loop below intentionally keeps a
    # cheap char/4 heuristic instead, since precision doesn't matter for
    # deciding roughly where a ~1600-token boundary falls, and calling a
    # real tokenizer per word would be unnecessarily slow on large docs.)
    return count_tokens(text)


def _split_into_sections(pages: list[RawPage]) -> list[tuple[SectionPath, str]]:
    """
    Walk pages line by line, tracking a heading stack. Any line matching a
    numbered-heading pattern (e.g. "3.2 Discount Rules") pushes/pops the
    stack to the right depth. Everything until the next heading belongs to
    that section.
    """
    sections: list[tuple[SectionPath, str]] = []
    heading_stack: list[str] = []
    buffer: list[str] = []
    section_start_page = pages[0].page_number if pages else 1

    def flush():
        if buffer and "".join(buffer).strip():
            sections.append(
                (
                    SectionPath(heading_trail=tuple(heading_stack), page_number=section_start_page),
                    "\n".join(buffer).strip(),
                )
            )
        buffer.clear()

    for page in pages:
        for line in page.text.splitlines():
            stripped = line.strip()
            match = _HEADING_PATTERN.match(stripped)
            if match and _looks_like_real_heading(match.group("title"), stripped):
                # Flush the PREVIOUS section using the page it actually
                # started on, then begin tracking the new section starting
                # at the current page.
                flush()
                section_start_page = page.page_number
                depth = match.group("marker").count(".") + 1
                title = f"{match.group('marker')} {match.group('title')}"
                heading_stack = heading_stack[: depth - 1] + [title]
            else:
                buffer.append(line)
    flush()
    return sections


def build_parent_child_chunks(
    pages: list[RawPage],
    document_id: str,
    document_name: str,
    version: str,
    parent_token_budget: int = 1600,
    child_token_budget: int = 400,
    child_overlap_tokens: int = 60,
) -> list[DocumentChunk]:
    """Returns a flat list of PARENT and CHILD DocumentChunk objects ready for embedding."""
    sections = _split_into_sections(pages)
    chunks: list[DocumentChunk] = []

    for section_path, text in sections:
        # A section might itself exceed the parent budget (e.g. a big table);
        # split into multiple parents in that case, each keeping the same
        # heading trail so citations stay accurate.
        words = text.split()
        parent_texts: list[str] = []
        cur: list[str] = []
        cur_tokens = 0
        for w in words:
            cur.append(w)
            cur_tokens += max(1, len(w) // 4)
            if cur_tokens >= parent_token_budget:
                parent_texts.append(" ".join(cur))
                cur, cur_tokens = [], 0
        if cur:
            parent_texts.append(" ".join(cur))

        for parent_text in parent_texts:
            parent_id = str(uuid.uuid4())
            chunks.append(
                DocumentChunk(
                    chunk_id=parent_id,
                    document_id=document_id,
                    document_name=document_name,
                    version=version,
                    content=parent_text,
                    section=section_path,
                    chunk_type=ChunkType.PARENT,
                    token_count=_approx_token_count(parent_text),
                )
            )

            # Slide a window over the parent to build children with overlap.
            p_words = parent_text.split()
            step = max(1, (child_token_budget - child_overlap_tokens))
            # convert token budget to an approx word-count window (~0.75 words/token)
            window_words = max(20, int(child_token_budget * 0.75))
            step_words = max(10, int(step * 0.75))

            i = 0
            while i < len(p_words):
                child_words = p_words[i : i + window_words]
                if not child_words:
                    break
                child_text = " ".join(child_words)
                chunks.append(
                    DocumentChunk(
                        chunk_id=str(uuid.uuid4()),
                        document_id=document_id,
                        document_name=document_name,
                        version=version,
                        content=child_text,
                        section=section_path,
                        chunk_type=ChunkType.CHILD,
                        parent_chunk_id=parent_id,
                        token_count=_approx_token_count(child_text),
                    )
                )
                if i + window_words >= len(p_words):
                    break
                i += step_words

    return chunks
