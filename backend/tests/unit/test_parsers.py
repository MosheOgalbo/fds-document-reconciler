"""Parser edge-case tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.exceptions.errors import DocumentParsingError
from app.infrastructure.parsing.parsers import parse_document, parse_docx, parse_pdf


def test_unsupported_extension_raises(tmp_path: Path):
    bad = tmp_path / "notes.txt"
    bad.write_text("hello", encoding="utf-8")
    with pytest.raises(DocumentParsingError, match="Unsupported"):
        parse_document(bad)


def test_missing_pdf_raises(tmp_path: Path):
    with pytest.raises(DocumentParsingError, match="not found|Failed to parse PDF"):
        parse_pdf(tmp_path / "does-not-exist.pdf")


def test_empty_docx_raises(tmp_path: Path):
    pytest.importorskip("docx")
    from docx import Document

    path = tmp_path / "empty.docx"
    Document().save(path)
    with pytest.raises(DocumentParsingError, match="no extractable text"):
        parse_docx(path)
