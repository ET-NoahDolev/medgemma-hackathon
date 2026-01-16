import pytest

from evaluation import metrics


def test_extraction_f1_returns_float() -> None:
    score = metrics.extraction_f1(["age >= 18"], ["age >= 18"])

    assert score == 1.0


def test_snomed_top1_accuracy_returns_float() -> None:
    score = metrics.snomed_top1_accuracy(["372244006"], ["372244006"])

    assert score == 1.0


def test_field_mapping_accuracy_returns_float() -> None:
    score = metrics.field_mapping_accuracy(
        ["demographics.age|>|75"], ["demographics.age|>|75"]
    )

    assert score == 1.0


def test_hitl_acceptance_rate_returns_float() -> None:
    score = metrics.hitl_acceptance_rate(["accept", "reject", "accept"])

    assert score == 2 / 3


def test_metrics_raise_on_empty_inputs() -> None:
    with pytest.raises(ValueError):
        metrics.extraction_f1([], [])

    with pytest.raises(ValueError):
        metrics.snomed_top1_accuracy([], [])

    with pytest.raises(ValueError):
        metrics.field_mapping_accuracy([], [])

    with pytest.raises(ValueError):
        metrics.hitl_acceptance_rate([])
