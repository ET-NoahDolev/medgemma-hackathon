from extraction_service import pipeline


def test_criterion_dataclass_fields() -> None:
    criterion = pipeline.Criterion(
        text="Age >= 18 years",
        criterion_type="inclusion",
        confidence=0.92,
    )

    assert criterion.text == "Age >= 18 years"
    assert criterion.criterion_type == "inclusion"
    assert criterion.confidence == 0.92


def test_extract_criteria_returns_list() -> None:
    criteria = pipeline.extract_criteria("Inclusion: Age >= 18 years.")

    assert isinstance(criteria, list)
    assert len(criteria) == 1
    assert criteria[0].text == "Age >= 18 years"


def test_split_into_candidate_sentences_returns_list() -> None:
    sentences = pipeline.split_into_candidate_sentences(
        "Inclusion: Age >= 18. Exclusion: Pregnant."
    )

    assert isinstance(sentences, list)
    assert sentences == ["Age >= 18", "Pregnant"]


def test_classify_criterion_type_returns_inclusion() -> None:
    label = pipeline.classify_criterion_type("Age >= 18 years")

    assert label == "inclusion"


def test_classify_criterion_type_returns_exclusion() -> None:
    label = pipeline.classify_criterion_type("Exclusion: Pregnant")

    assert label == "exclusion"
