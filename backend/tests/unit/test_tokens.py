from app.core.tokens import count_tokens, truncate_to_token_budget


def test_count_tokens_never_raises_and_returns_positive_for_nonempty_text():
    assert count_tokens("hello world") > 0


def test_count_tokens_empty_string_is_zero():
    assert count_tokens("") == 0


def test_count_tokens_is_deterministic():
    text = "The NA uplift is +25% for HW/Accessories."
    assert count_tokens(text) == count_tokens(text)


def test_truncate_returns_unchanged_text_when_under_budget():
    text = "short text"
    assert truncate_to_token_budget(text, budget=1000) == text


def test_truncate_shortens_text_when_over_budget():
    long_text = "word " * 5000  # comfortably exceeds any reasonable small budget
    result = truncate_to_token_budget(long_text, budget=10)
    assert len(result) < len(long_text)
    assert "truncated" in result


def test_truncate_empty_string_is_safe():
    assert truncate_to_token_budget("", budget=100) == ""
