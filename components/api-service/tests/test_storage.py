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


@dataclass
class FakeCriterion:
    text: str
    criterion_type: str
    confidence: float
