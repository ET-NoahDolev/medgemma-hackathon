from shared import models


def test_build_criterion_defaults() -> None:
    criterion = models.build_criterion()

    assert criterion.id == "crit-1"
    assert criterion.text == "Age >= 18 years"
    assert criterion.criterion_type == "inclusion"
    assert criterion.confidence == 0.92
    assert criterion.snomed_codes == ["371273006"]


def test_build_criterion_custom_codes() -> None:
    criterion = models.build_criterion(
        id="crit-2",
        snomed_codes=["123"],
        criterion_type="exclusion",
    )

    assert criterion.id == "crit-2"
    assert criterion.criterion_type == "exclusion"
    assert criterion.snomed_codes == ["123"]


def test_build_field_mapping_allows_none_confidence() -> None:
    mapping = models.build_field_mapping(confidence=None)

    assert mapping.confidence is None
    assert mapping.field == "demographics.age"
    assert mapping.relation == ">="
    assert mapping.value == "18"


def test_build_protocol_and_document() -> None:
    protocol = models.build_protocol()
    document = models.build_document()

    assert protocol.id == "proto-1"
    assert document.protocol_id == "proto-1"


def test_build_grounding_candidate_and_hitl_edit() -> None:
    candidate = models.build_grounding_candidate()
    edit = models.build_hitl_edit()

    assert candidate.code == "372244006"
    assert edit.action == "accept"
