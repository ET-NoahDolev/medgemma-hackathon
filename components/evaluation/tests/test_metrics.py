import pytest

from evaluation.metrics import (
    extraction_f1,
    field_mapping_accuracy,
    hitl_acceptance_rate,
    snomed_top1_accuracy,
)


class TestExtractionF1:
    def test_exact_match_returns_1(self) -> None:
        pred = ["Age >= 18", "ECOG 0-1"]
        gold = ["Age >= 18", "ECOG 0-1"]
        assert extraction_f1(pred, gold) == 1.0

    def test_no_overlap_returns_0(self) -> None:
        pred = ["Age >= 18"]
        gold = ["BMI < 30"]
        assert extraction_f1(pred, gold) == 0.0

    def test_partial_overlap(self) -> None:
        pred = ["Age >= 18", "ECOG 0-1", "Extra"]
        gold = ["Age >= 18", "ECOG 0-1"]
        f1 = extraction_f1(pred, gold)
        assert 0.0 < f1 < 1.0

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            extraction_f1([], ["Age >= 18"])


class TestSnomedTop1Accuracy:
    def test_all_correct(self) -> None:
        pred = ["12345", "67890"]
        gold = ["12345", "67890"]
        assert snomed_top1_accuracy(pred, gold) == 1.0

    def test_none_correct(self) -> None:
        pred = ["12345", "67890"]
        gold = ["11111", "22222"]
        assert snomed_top1_accuracy(pred, gold) == 0.0

    def test_partial_correct(self) -> None:
        pred = ["12345", "wrong"]
        gold = ["12345", "67890"]
        assert snomed_top1_accuracy(pred, gold) == 0.5


class TestFieldMappingAccuracy:
    def test_exact_match(self) -> None:
        pred = ["demographics.age|>=|18"]
        gold = ["demographics.age|>=|18"]
        assert field_mapping_accuracy(pred, gold) == 1.0


class TestHitlAcceptanceRate:
    def test_all_accept(self) -> None:
        assert hitl_acceptance_rate(["accept", "accept", "accept"]) == 1.0

    def test_all_reject(self) -> None:
        assert hitl_acceptance_rate(["reject", "reject"]) == 0.0

    def test_mixed(self) -> None:
        assert hitl_acceptance_rate(["accept", "reject", "accept"]) == pytest.approx(
            2 / 3
        )

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            hitl_acceptance_rate([])
