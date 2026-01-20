from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pytest

from api_service.storage import Storage, get_engine, reset_storage


@pytest.fixture()
def storage() -> Storage:
    reset_storage()
    return Storage(get_engine())


class TestProtocolSchema:
    def test_protocol_has_nct_id_column(self, storage: Storage) -> None:
        proto = storage.create_protocol(
            title="Test",
            document_text="Text",
            nct_id="NCT12345678",
            condition="Melanoma",
            phase="Phase 2",
        )

        assert proto.nct_id == "NCT12345678"

    def test_protocol_has_condition_column(self, storage: Storage) -> None:
        proto = storage.create_protocol(
            title="Test",
            document_text="Text",
            nct_id="NCT12345678",
            condition="Melanoma",
            phase="Phase 2",
        )

        assert proto.condition == "Melanoma"

    def test_protocol_has_source_column(self, storage: Storage) -> None:
        proto = storage.create_protocol(
            title="Test",
            document_text="Text",
            source="bmjopen",
        )

        assert proto.source == "bmjopen"


class TestHitlEditTable:
    def test_create_hitl_edit(self, storage: Storage) -> None:
        proto = storage.create_protocol(title="T", document_text="Age >= 18")
        storage.replace_criteria(
            protocol_id=proto.id,
            extracted=[
                FakeCriterion(
                    text="Age >= 18",
                    criterion_type="inclusion",
                    confidence=0.9,
                )
            ],
        )
        criteria = storage.list_criteria(proto.id)
        crit_id = criteria[0].id

        edit = storage.create_hitl_edit(
            criterion_id=crit_id,
            action="accept",
            snomed_code_added="371273006",
            note="Verified correct",
        )

        assert edit.id.startswith("edit-")
        assert edit.criterion_id == crit_id
        assert edit.action == "accept"
        assert edit.snomed_code_added == "371273006"

    def test_list_hitl_edits_by_criterion(self, storage: Storage) -> None:
        proto = storage.create_protocol(title="T", document_text="Age >= 18")
        storage.replace_criteria(
            protocol_id=proto.id,
            extracted=[
                FakeCriterion(
                    text="Age >= 18",
                    criterion_type="inclusion",
                    confidence=0.9,
                )
            ],
        )
        crit_id = storage.list_criteria(proto.id)[0].id

        storage.create_hitl_edit(criterion_id=crit_id, action="accept")
        storage.create_hitl_edit(criterion_id=crit_id, action="edit", note="Changed")

        edits = storage.list_hitl_edits(crit_id)
        assert len(edits) == 2

    def test_hitl_edit_has_created_at(self, storage: Storage) -> None:
        proto = storage.create_protocol(title="T", document_text="Text")
        storage.replace_criteria(
            protocol_id=proto.id,
            extracted=[
                FakeCriterion(
                    text="Text",
                    criterion_type="inclusion",
                    confidence=0.9,
                )
            ],
        )
        crit_id = storage.list_criteria(proto.id)[0].id

        edit = storage.create_hitl_edit(criterion_id=crit_id, action="accept")

        assert isinstance(edit.created_at, datetime)


class TestSnomedCodeManagement:
    def test_add_snomed_code_to_criterion(self, storage: Storage) -> None:
        proto = storage.create_protocol(title="T", document_text="Age >= 18")
        storage.replace_criteria(
            protocol_id=proto.id,
            extracted=[
                FakeCriterion(
                    text="Age >= 18",
                    criterion_type="inclusion",
                    confidence=0.9,
                )
            ],
        )
        crit_id = storage.list_criteria(proto.id)[0].id

        updated = storage.add_snomed_code(criterion_id=crit_id, code="371273006")

        assert updated is not None
        assert updated.snomed_codes == ["371273006"]

    def test_add_snomed_code_idempotent(self, storage: Storage) -> None:
        proto = storage.create_protocol(title="T", document_text="Age >= 18")
        storage.replace_criteria(
            protocol_id=proto.id,
            extracted=[
                FakeCriterion(
                    text="Age >= 18",
                    criterion_type="inclusion",
                    confidence=0.9,
                )
            ],
        )
        crit_id = storage.list_criteria(proto.id)[0].id

        storage.add_snomed_code(criterion_id=crit_id, code="371273006")
        updated = storage.add_snomed_code(criterion_id=crit_id, code="371273006")

        assert updated is not None
        assert updated.snomed_codes == ["371273006"]

    def test_remove_snomed_code_from_criterion(self, storage: Storage) -> None:
        proto = storage.create_protocol(title="T", document_text="Age >= 18")
        storage.replace_criteria(
            protocol_id=proto.id,
            extracted=[
                FakeCriterion(
                    text="Age >= 18",
                    criterion_type="inclusion",
                    confidence=0.9,
                )
            ],
        )
        crit_id = storage.list_criteria(proto.id)[0].id
        storage.add_snomed_code(criterion_id=crit_id, code="371273006")

        updated = storage.remove_snomed_code(
            criterion_id=crit_id, code="371273006"
        )

        assert updated is not None
        assert updated.snomed_codes == []

    def test_remove_nonexistent_code_no_error(self, storage: Storage) -> None:
        proto = storage.create_protocol(title="T", document_text="Age >= 18")
        storage.replace_criteria(
            protocol_id=proto.id,
            extracted=[
                FakeCriterion(
                    text="Age >= 18",
                    criterion_type="inclusion",
                    confidence=0.9,
                )
            ],
        )
        crit_id = storage.list_criteria(proto.id)[0].id

        updated = storage.remove_snomed_code(
            criterion_id=crit_id, code="371273006"
        )

        assert updated is not None
        assert updated.snomed_codes == []


class TestProtocolListing:
    def test_list_protocols_empty(self, storage: Storage) -> None:
        protocols, total = storage.list_protocols()

        assert protocols == []
        assert total == 0

    def test_list_protocols_returns_all(self, storage: Storage) -> None:
        storage.create_protocol(title="T1", document_text="Text 1")
        storage.create_protocol(title="T2", document_text="Text 2")

        protocols, total = storage.list_protocols()

        assert total == 2
        assert [protocol.title for protocol in protocols] == ["T1", "T2"]

    def test_list_protocols_pagination(self, storage: Storage) -> None:
        for i in range(15):
            storage.create_protocol(title=f"T{i}", document_text=f"Text {i}")

        page_one, total = storage.list_protocols(skip=0, limit=10)
        page_two, _ = storage.list_protocols(skip=10, limit=10)

        assert total == 15
        assert len(page_one) == 10
        assert len(page_two) == 5

    def test_list_protocols_returns_total_count(self, storage: Storage) -> None:
        storage.create_protocol(title="T1", document_text="Text 1")
        storage.create_protocol(title="T2", document_text="Text 2")
        storage.create_protocol(title="T3", document_text="Text 3")

        _, total = storage.list_protocols(skip=1, limit=1)

        assert total == 3


@dataclass
class FakeCriterion:
    text: str
    criterion_type: str
    confidence: float
