from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from api_service import main as api_main
from api_service.main import app
from api_service.storage import reset_storage
from tests import constants


@dataclass
class FakeExtractedCriterion:
    text: str
    criterion_type: str
    confidence: float


@dataclass
class FakeGroundingCandidate:
    code: str
    display: str
    confidence: float


@dataclass
class FakeFieldMapping:
    field: str
    relation: str
    value: str
    confidence: float


@dataclass
class FakeServicesState:
    extracted: list[FakeExtractedCriterion]
    candidates: list[FakeGroundingCandidate]
    field_mappings: list[FakeFieldMapping]


@pytest.fixture()
def client() -> TestClient:
    reset_storage()
    return TestClient(app)


@pytest.fixture()
def fake_services(monkeypatch: pytest.MonkeyPatch) -> FakeServicesState:
    state = FakeServicesState(
        extracted=[
            FakeExtractedCriterion(
                text=constants.EXTRACTED_TEXT,
                criterion_type=constants.CRITERION_TYPE,
                confidence=constants.CRITERION_CONFIDENCE,
            )
        ],
        candidates=[
            FakeGroundingCandidate(
                code=constants.SNOMED_CODE,
                display="Age (finding)",
                confidence=0.88,
            )
        ],
        field_mappings=[
            FakeFieldMapping(
                field=constants.FIELD_MAPPING_FIELD,
                relation=">=",
                value="18",
                confidence=0.77,
            )
        ],
    )

    def _extract_criteria(_text: str) -> list[FakeExtractedCriterion]:
        return state.extracted

    class FakeUmlsClient:
        def search_snomed(self, _text: str) -> list[FakeGroundingCandidate]:
            return state.candidates

    def _propose_field_mapping(_text: str) -> list[FakeFieldMapping]:
        return state.field_mappings

    monkeypatch.setattr(
        api_main.extraction_pipeline, "extract_criteria", _extract_criteria
    )
    monkeypatch.setattr(api_main.umls_client, "UmlsClient", FakeUmlsClient)
    monkeypatch.setattr(
        api_main.umls_client, "propose_field_mapping", _propose_field_mapping
    )

    return state
