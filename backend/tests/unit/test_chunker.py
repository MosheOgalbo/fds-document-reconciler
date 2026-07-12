from app.domain.entities.document import ChunkType
from app.infrastructure.parsing.chunker import RawPage, build_parent_child_chunks


def test_heading_hierarchy_is_preserved():
    pages = [
        RawPage(
            page_number=1,
            text=(
                "1 Overview\n"
                "This is the overview section with some content.\n"
                "1.1 Scope\n"
                "This describes the scope of the document in detail.\n"
            ),
        ),
        RawPage(
            page_number=2,
            text=(
                "2 Pricing\n"
                "2.1 Discounts\n"
                "Discount rules are described here at length.\n"
            ),
        ),
    ]

    chunks = build_parent_child_chunks(pages, document_id="doc-1", document_name="FDS.pdf", version="v1")

    assert len(chunks) > 0
    parents = [c for c in chunks if c.chunk_type == ChunkType.PARENT]
    children = [c for c in chunks if c.chunk_type == ChunkType.CHILD]
    assert len(parents) >= 3  # Overview, Scope, Discounts sections
    assert len(children) >= len(parents)

    scope_parent = next(p for p in parents if "Scope" in p.section.as_breadcrumb())
    assert scope_parent.section.page_number == 1
    assert "1 Overview" in scope_parent.section.heading_trail[0]

    discount_parent = next(p for p in parents if "Discounts" in p.section.as_breadcrumb())
    assert discount_parent.section.page_number == 2


def test_children_reference_their_parent():
    pages = [RawPage(page_number=1, text="1 Intro\n" + ("word " * 500))]
    chunks = build_parent_child_chunks(pages, document_id="doc-2", document_name="Test.pdf", version="v1")

    parents = {c.chunk_id for c in chunks if c.chunk_type == ChunkType.PARENT}
    children = [c for c in chunks if c.chunk_type == ChunkType.CHILD]

    assert children, "expected at least one child chunk for a long section"
    for child in children:
        assert child.parent_chunk_id in parents


def test_metadata_contains_required_fields():
    pages = [RawPage(page_number=1, text="1 Section A\nSome content here.")]
    chunks = build_parent_child_chunks(pages, document_id="doc-3", document_name="Spec.docx", version="v2")

    for chunk in chunks:
        meta = chunk.to_metadata()
        for field_name in ("document", "version", "page", "section", "chunk_id", "filename"):
            assert field_name in meta


def test_trailing_period_heading_format_is_recognized():
    """Regression test: real-world docs often use '1. Title' (trailing period
    after the number) rather than '1 Title'. Found via testing against the
    actual FDS_PriceBook sample PDF, where this format caused every
    top-level heading to be silently missed."""
    pages = [
        RawPage(page_number=1, text="1. Executive Summary\nSome overview text.\n2. The Business Challenge\nMore text."),
    ]
    chunks = build_parent_child_chunks(pages, document_id="doc-4", document_name="Spec.pdf", version="v1")
    parents = [c for c in chunks if c.chunk_type == ChunkType.PARENT]
    breadcrumbs = [p.section.as_breadcrumb() for p in parents]
    assert any("Executive Summary" in b for b in breadcrumbs)
    assert any("Business Challenge" in b for b in breadcrumbs)


def test_numbered_file_hierarchy_table_rows_are_not_headings():
    """Regression: borderless numbered tables in the sample PDF (File Hierarchy)
    must stay inside their parent section, not become spurious headings."""
    pages = [
        RawPage(
            page_number=2,
            text=(
                "3.2 File Hierarchy\n"
                "# File Derived From Purpose\n"
                "1 PM PB (Q2-26v1) PM PB Q2-26v0 Final PM input\n"
                "2 Macro PB (.xlsm) PM PB v1 Master file\n"
                "3 Channel PB - ACTS USD Macro PB ROW channel book\n"
                "Real section body after the table.\n"
            ),
        )
    ]
    chunks = build_parent_child_chunks(pages, document_id="doc-6", document_name="Spec.pdf", version="v1")
    parents = [c for c in chunks if c.chunk_type == ChunkType.PARENT]
    breadcrumbs = [p.section.as_breadcrumb() for p in parents]
    assert any("File Hierarchy" in b for b in breadcrumbs)
    assert not any("PM PB (Q2-26v1)" in b for b in breadcrumbs)
    assert not any("Macro PB (.xlsm)" in b for b in breadcrumbs)
    assert not any("Channel PB - ACTS USD" in b for b in breadcrumbs)
    hierarchy_parent = next(p for p in parents if "File Hierarchy" in p.section.as_breadcrumb())
    assert "PM PB (Q2-26v1)" in hierarchy_parent.content
    assert "Real section body after the table." in hierarchy_parent.content


def test_wrapped_lowercase_body_text_is_not_mistaken_for_a_heading():
    """Regression test: PDF line-wrapping can put a bare number at the start
    of a wrapped sentence fragment (e.g. '15 manual validation rules are
    executed...'). This must NOT be treated as a new heading — confirmed
    against the actual sample PDF where this previously corrupted the
    section hierarchy."""
    pages = [
        RawPage(
            page_number=1,
            text=(
                "1. Executive Summary\n"
                "The process requires review.\n"
                "15 manual validation rules are executed before the file can be\n"
                "handed off to the next stage.\n"
            ),
        )
    ]
    chunks = build_parent_child_chunks(pages, document_id="doc-5", document_name="Spec.pdf", version="v1")
    parents = [c for c in chunks if c.chunk_type == ChunkType.PARENT]
    breadcrumbs = [p.section.as_breadcrumb() for p in parents]
    # Only ONE real heading should be detected — the wrapped "15 manual..."
    # line must be folded into the Executive Summary section's body text,
    # not treated as its own heading.
    assert breadcrumbs == ["1. Executive Summary"] or breadcrumbs == ["1 Executive Summary"]
    combined_text = next(c.content for c in chunks if c.chunk_type == ChunkType.PARENT)
    assert "15 manual validation rules" in combined_text
