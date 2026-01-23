from extraction_service.pipeline import iter_normalized_texts, normalize_criterion_text


def test_normalize_criterion_text_collapses_whitespace() -> None:
    text = "  Age   >=   18 years.  "
    assert normalize_criterion_text(text) == "Age >= 18 years"


def test_iter_normalized_texts_yields_normalized_items() -> None:
    raw = ["  A  .", "B", "  C   "]
    assert list(iter_normalized_texts(raw)) == ["A", "B", "C"]
