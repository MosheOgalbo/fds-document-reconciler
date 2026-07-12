"""
Pure table-formatting helper — deliberately has zero dependency on pdfplumber
or python-docx so it can be unit tested without either library installed.
Both parsers extract raw table rows (list[list[str]]) using their own
format-specific APIs, then hand them to this function to produce a
consistent Markdown representation that:
  (a) keeps rows/columns machine-readable for the LLM (pricing tables are
      exactly where the business rules live in a Price Book spec), and
  (b) flows naturally into the same heading-based chunker as prose text,
      since it's just text lines.
"""
from __future__ import annotations


def table_rows_to_markdown(rows: list[list[str]]) -> str:
    """Convert a list of table rows (list of cell strings) into a Markdown table.
    Returns an empty string for empty/degenerate input rather than raising,
    since malformed tables are common in real-world scanned/exported docs
    and shouldn't abort the whole parse."""
    if not rows or not rows[0]:
        return ""

    def clean(cell) -> str:
        return (str(cell) if cell is not None else "").strip().replace("\n", " ").replace("|", "\\|")

    header = [clean(c) for c in rows[0]]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]

    for row in rows[1:]:
        cells = [clean(c) for c in row]
        # Pad/truncate ragged rows to header width so the Markdown stays valid.
        if len(cells) < len(header):
            cells += [""] * (len(header) - len(cells))
        elif len(cells) > len(header):
            cells = cells[: len(header)]
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)
