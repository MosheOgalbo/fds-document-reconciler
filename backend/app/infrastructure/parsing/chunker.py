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
from app.infrastructure.parsing.table_chunking import (
    prose_window_child_texts,
    split_parent_texts,
    table_row_child_texts,
)

_HEADING_PATTERN = re.compile(
    r"^(?P<marker>\d+(?:\.\d+)*)\.?\s+(?P<title>\S.*)$"
)

_MD_HEADING_PATTERN = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>\S.+)$")

_MAX_HEADING_LINE_LENGTH = 80

# Numbered table rows in borderless PDF tables (e.g. the sample's "File
# Hierarchy" list) match the heading regex but are not section titles.
_TABLE_ROW_HINT = re.compile(
    r"(\.(xlsm|xlsx|pdf|docx)\b"  # file extensions in a "title" → table row
    r"|\(Q\d"  # quarter version refs like (Q2-26v1)
    r"|\bPM PB \("
    r"|\bMacro PB\b"
    r"|\bChannel PB -"
    r"|\bACM PB -"
    r"|\bDistributor PB\b"
    r"|\+\s*(Python|rate)\b"
    r"|;\s*$"  # purpose column trailing semicolon from table extraction
    r")",
    re.IGNORECASE,
)


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

    Heuristics (no font-size metadata needed):
    - real headings are short; table rows often aren't
    - title starts with a capital letter (wrapped fragments start lowercase)
    - table rows carry file names, extensions, or quarter-version parentheses
    """
    if len(full_line) > _MAX_HEADING_LINE_LENGTH:
        return False
    if not title[:1].isupper():
        return False
    if _TABLE_ROW_HINT.search(title):
        return False
    return True


def _looks_like_markdown_table_header(title: str) -> bool:
    """PDF table headers are sometimes extracted as '# Col1 Col2 Col3' lines."""
    words = [w for w in title.split() if w]
    return len(words) >= 3 and all(w[0].isupper() for w in words)


def _parse_heading_line(stripped: str) -> tuple[int, str] | None:
    """Return (depth, title) when a line is a section heading."""
    md = _MD_HEADING_PATTERN.match(stripped)
    if md:
        title = md.group("title").strip()
        depth = len(md.group("hashes"))
        if not title or len(stripped) > _MAX_HEADING_LINE_LENGTH:
            return None
        if depth == 1 and _looks_like_markdown_table_header(title):
            return None
        return depth, title

    match = _HEADING_PATTERN.match(stripped)
    if match and _looks_like_real_heading(match.group("title"), stripped):
        depth = match.group("marker").count(".") + 1
        title = f"{match.group('marker')} {match.group('title')}"
        return depth, title
    return None


def _maybe_fallback_page_sections(
    pages: list[RawPage],
    sections: list[tuple[SectionPath, str]],
) -> list[tuple[SectionPath, str]]:
    """
    When heading detection collapses a multi-page PDF into one section, fall back
    to page-level sections so chunk counts reflect the full document.
    """
    if len(sections) > 1 or len(pages) < 2:
        return sections

    total_chars = sum(len(p.text or "") for p in pages)
    if total_chars < 2000:
        return sections

    fallback: list[tuple[SectionPath, str]] = []
    for page in pages:
        text = (page.text or "").strip()
        if not text:
            continue
        fallback.append(
            (
                SectionPath(heading_trail=(f"Page {page.page_number}",), page_number=page.page_number),
                text,
            )
        )
    return fallback if len(fallback) >= 2 else sections


def _maybe_fallback_paragraph_sections(
    pages: list[RawPage],
    sections: list[tuple[SectionPath, str]],
) -> list[tuple[SectionPath, str]]:
    """
    Single-page documents (typical DOCX) with no detected headings: split on
    blank lines when the body is long enough to need multiple chunks.
    """
    if len(sections) != 1:
        return sections

    section_path, text = sections[0]
    if len(text) < 1200:
        return sections

    blocks = [b.strip() for b in re.split(r"\n{2,}", text) if b.strip()]
    if len(blocks) < 3:
        return sections

    page_number = section_path.page_number or (pages[0].page_number if pages else 1)
    return [
        (
            SectionPath(heading_trail=(f"Section {idx + 1}",), page_number=page_number),
            block,
        )
        for idx, block in enumerate(blocks)
    ]


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
            parsed = _parse_heading_line(stripped)
            if parsed:
                flush()
                section_start_page = page.page_number
                depth, title = parsed
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
    sections = _maybe_fallback_page_sections(pages, sections)
    sections = _maybe_fallback_paragraph_sections(pages, sections)
    chunks: list[DocumentChunk] = []
    chunk_index = 0
    # Approximate character offset across the concatenated section stream so
    # citations can point back near the original text position.
    char_cursor = 0

    for section_path, text in sections:
        parent_texts = split_parent_texts(text, parent_token_budget, _approx_token_count)

        for parent_text in parent_texts:
            parent_id = str(uuid.uuid4())
            parent_offset = char_cursor
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
                    chunk_index=chunk_index,
                    char_offset=parent_offset,
                )
            )
            chunk_index += 1

            child_texts: list[str] = []
            child_texts.extend(table_row_child_texts(parent_text))
            child_texts.extend(
                prose_window_child_texts(
                    parent_text,
                    child_token_budget=child_token_budget,
                    child_overlap_tokens=child_overlap_tokens,
                )
            )

            # Dedupe identical child spans (table rows can overlap prose windows).
            seen: set[str] = set()
            for child_text in child_texts:
                key = child_text.strip()
                if not key or key in seen:
                    continue
                seen.add(key)
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
                        chunk_index=chunk_index,
                        char_offset=parent_offset,
                    )
                )
                chunk_index += 1

            char_cursor = parent_offset + len(parent_text) + 2

    return chunks
