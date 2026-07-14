from app.infrastructure.parsing.table_chunking import count_markdown_table_stats, table_row_child_texts


def test_count_markdown_table_stats():
    text = (
        "| A | B |\n"
        "| --- | --- |\n"
        "| 1 | 2 |\n"
        "| 3 | 4 |\n"
        "\n"
        "Some prose.\n"
        "\n"
        "| X | Y |\n"
        "| --- | --- |\n"
        "| foo | bar |\n"
    )
    tables, rows = count_markdown_table_stats(text)
    assert tables == 2
    assert rows == 3


def test_table_row_child_texts_includes_header():
    block = "| Col1 | Col2 |\n| --- | --- |\n| alpha | beta |\n| gamma | delta |\n"
    children = table_row_child_texts(block, rows_per_child=1)
    assert len(children) == 2
    assert all("| Col1 | Col2 |" in c for c in children)
    assert any("alpha" in c for c in children)
    assert any("gamma" in c for c in children)
