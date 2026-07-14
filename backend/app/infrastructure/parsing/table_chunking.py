"""
Table-aware text segmentation for parent/child chunking.

Markdown tables must keep their row boundaries — word-splitting parent text
destroys `| col |` structure and makes row-level retrieval impossible.
"""
from __future__ import annotations

import re

_TABLE_SEP_RE = re.compile(r"^\|\s*:?-{2,}")


def contains_markdown_table(text: str) -> bool:
    return "|" in text and any(_TABLE_SEP_RE.search(line) for line in text.splitlines())


def split_parent_texts(text: str, token_budget: int, approx_tokens) -> list[str]:
    """
    Split section text into parent-sized spans while preserving block structure
    (especially markdown table line breaks).
    """
    if not text.strip():
        return []

    if contains_markdown_table(text):
        blocks = [b.strip() for b in re.split(r"\n{2,}", text) if b.strip()]
        if not blocks:
            blocks = [text.strip()]
    else:
        blocks = [text.strip()]

    parents: list[str] = []
    cur: list[str] = []
    cur_tokens = 0

    for block in blocks:
        block_tokens = approx_tokens(block)
        if block_tokens >= token_budget and contains_markdown_table(block):
            if cur:
                parents.append("\n\n".join(cur))
                cur, cur_tokens = [], 0
            parents.extend(_split_large_table_block(block, token_budget, approx_tokens))
            continue

        if cur_tokens + block_tokens > token_budget and cur:
            parents.append("\n\n".join(cur))
            cur, cur_tokens = [], 0

        cur.append(block)
        cur_tokens += block_tokens

    if cur:
        parents.append("\n\n".join(cur))
    return parents or [text.strip()]


def _split_large_table_block(block: str, token_budget: int, approx_tokens) -> list[str]:
    """Split an oversized table into row-group parents that keep a shared header."""
    lines = [ln for ln in block.splitlines() if ln.strip()]
    header: str | None = None
    sep: str | None = None
    data_rows: list[str] = []

    for line in lines:
        if not line.strip().startswith("|"):
            continue
        if _TABLE_SEP_RE.search(line):
            sep = line
            continue
        if header is None:
            header = line
        else:
            data_rows.append(line)

    if not header or not data_rows:
        return [block]

    header_block = "\n".join(x for x in [header, sep] if x)
    groups: list[str] = []
    batch: list[str] = []
    batch_tokens = approx_tokens(header_block)

    for row in data_rows:
        row_tokens = approx_tokens(row)
        if batch and batch_tokens + row_tokens > token_budget:
            groups.append(header_block + "\n" + "\n".join(batch))
            batch, batch_tokens = [], approx_tokens(header_block)
        batch.append(row)
        batch_tokens += row_tokens

    if batch:
        groups.append(header_block + "\n" + "\n".join(batch))
    return groups or [block]


def table_row_child_texts(parent_text: str, rows_per_child: int = 8) -> list[str]:
    """Child chunks for markdown tables — groups rows to limit embedding API calls."""
    if not contains_markdown_table(parent_text):
        return []

    lines = [ln for ln in parent_text.splitlines() if ln.strip()]
    header: str | None = None
    sep: str | None = None
    data_rows: list[str] = []

    for line in lines:
        if not line.strip().startswith("|"):
            continue
        if _TABLE_SEP_RE.search(line):
            sep = line
            continue
        if header is None:
            header = line
            continue
        data_rows.append(line)

    if not header or not data_rows:
        return []

    header_block = "\n".join(x for x in [header, sep] if x)
    group_size = max(1, rows_per_child)
    children: list[str] = []
    for i in range(0, len(data_rows), group_size):
        batch = data_rows[i : i + group_size]
        children.append(header_block + "\n" + "\n".join(batch))
    return children


def count_markdown_table_stats(text: str) -> tuple[int, int]:
    """Return (table_count, data_row_count) across concatenated page text."""
    table_count = 0
    data_rows = 0
    in_table = False
    header_seen = False

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            header_seen = False
            continue
        if _TABLE_SEP_RE.search(stripped):
            in_table = True
            header_seen = False
            continue
        if not in_table:
            table_count += 1
            in_table = True
            header_seen = True
            continue
        if header_seen:
            header_seen = False
            continue
        data_rows += 1

    return table_count, data_rows


def prose_window_child_texts(
    parent_text: str,
    *,
    child_token_budget: int,
    child_overlap_tokens: int,
) -> list[str]:
    """Sliding-window children for non-table prose within a parent."""
    if contains_markdown_table(parent_text):
        # Prose outside tables only — strip table blocks for windowing.
        prose_parts: list[str] = []
        buf: list[str] = []
        for line in parent_text.splitlines():
            if line.strip().startswith("|"):
                if buf:
                    prose_parts.append("\n".join(buf))
                    buf = []
                continue
            buf.append(line)
        if buf:
            prose_parts.append("\n".join(buf))
        text = "\n\n".join(p for p in prose_parts if p.strip())
    else:
        text = parent_text

    if not text.strip():
        return []

    words = text.split()
    window_words = max(20, int(child_token_budget * 0.75))
    step_words = max(10, int((child_token_budget - child_overlap_tokens) * 0.75))

    children: list[str] = []
    i = 0
    while i < len(words):
        chunk_words = words[i : i + window_words]
        if not chunk_words:
            break
        children.append(" ".join(chunk_words))
        if i + window_words >= len(words):
            break
        i += step_words
    return children
