from app.infrastructure.parsing.table_formatter import table_rows_to_markdown


def test_basic_table_conversion():
    rows = [["Product", "Price"], ["Widget A", "$10"], ["Widget B", "$20"]]
    md = table_rows_to_markdown(rows)
    assert "| Product | Price |" in md
    assert "| Widget A | $10 |" in md
    assert "| --- | --- |" in md


def test_empty_rows_returns_empty_string():
    assert table_rows_to_markdown([]) == ""
    assert table_rows_to_markdown([[]]) == ""


def test_ragged_rows_are_padded_to_header_width():
    rows = [["A", "B", "C"], ["1", "2"]]  # second row missing a cell
    md = table_rows_to_markdown(rows)
    lines = md.splitlines()
    data_line = lines[2]
    assert data_line.count("|") == lines[0].count("|")  # same column count as header


def test_none_cells_and_pipes_are_sanitized():
    rows = [["A", "B"], [None, "has | pipe"]]
    md = table_rows_to_markdown(rows)
    assert "\\|" in md  # pipe escaped so it doesn't break the markdown table
