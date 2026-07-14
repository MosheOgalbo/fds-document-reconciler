from app.domain.entities.document import ComparisonReport, DiffItem, MatchItem, MissingItem


def test_comparison_report_matches_exact_required_schema():
    """The brief requires EXACTLY this JSON shape — this test pins that
    contract down so a future refactor can't silently drift from it."""
    report = ComparisonReport(
        missing=[MissingItem(text="New clause", source_file="docB.docx", location="Page 5, Section 2.1")],
        diff=[
            DiffItem(
                docA_text="Uplift is 20%",
                docB_text="Uplift is 25%",
                reason="Percentage increased",
                sourceA="Page 3, Section 6",
                sourceB="Page 4, Section 6",
            )
        ],
        match=[MatchItem(textA="Same rule", textB="Same rule", source="docA.pdf / Page 2 + docB.docx / Page 2")],
    )

    result = report.to_dict()

    assert set(result.keys()) == {"missing", "diff", "match"}

    assert result["missing"] == [
        {"text": "New clause", "source_file": "docB.docx", "location": "Page 5, Section 2.1"}
    ]
    assert result["diff"] == [
        {
            "docA_text": "Uplift is 20%",
            "docB_text": "Uplift is 25%",
            "reason": "Percentage increased",
            "sourceA": "Page 3, Section 6",
            "sourceB": "Page 4, Section 6",
        }
    ]
    assert result["match"] == [
        {"textA": "Same rule", "textB": "Same rule", "source": "docA.pdf / Page 2 + docB.docx / Page 2"}
    ]


def test_comparison_report_includes_optional_similarity_when_set():
    report = ComparisonReport(
        missing=[],
        diff=[
            DiffItem(
                docA_text="A",
                docB_text="B",
                reason="changed",
                sourceA="Page 1",
                sourceB="Page 2",
                semantic_similarity=0.55,
            )
        ],
        match=[MatchItem(textA="x", textB="x", source="both", similarity_score=0.97)],
    )
    result = report.to_dict()
    assert result["diff"][0]["semantic_similarity"] == 0.55
    assert result["match"][0]["similarity_score"] == 0.97


def test_comparison_report_empty_categories_are_empty_lists_not_missing_keys():
    report = ComparisonReport()
    result = report.to_dict()
    assert result == {"missing": [], "diff": [], "match": []}
