from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

import api_service.ingestion as ingestion
import api_service.main as api_main
from api_service.main import app
from api_service.storage import reset_storage
from tests import constants

api_main_any = cast(Any, api_main)

@dataclass
class FakeExtractedCriterion:
    text: str
    criterion_type: str
    confidence: float


@dataclass
class FakeGroundingCandidate:
    code: str
    display: str
    ontology: str
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
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    reset_storage()
    # Avoid clobbering a real UMLS_API_KEY loaded from repo root .env.
    monkeypatch.setenv("GROUNDING_SERVICE_UMLS_API_KEY", "test-key")
    return TestClient(app)


@pytest.fixture(autouse=True)
def allow_storage_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_STORAGE_RESET", "1")


@pytest.fixture(autouse=True)
def force_fast_test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force fast, deterministic settings for tests.

    BackgroundTasks can execute extraction during request handling. Ensure we do
    not accidentally invoke model-backed extraction/grounding in unit tests.
    """

    monkeypatch.setenv("USE_MODEL_EXTRACTION", "false")
    monkeypatch.setenv("USE_AI_GROUNDING", "false")


@pytest.fixture(autouse=True)
def stub_model_extraction(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Stub extraction to keep tests deterministic."""
    if "fake_services" in request.fixturenames:
        return

    async def _extract_criteria_async(
        _text: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> list[FakeExtractedCriterion]:
        _ = session_id  # Unused but required for signature compatibility
        _ = user_id  # Unused but required for signature compatibility
        return [
            FakeExtractedCriterion(
                text=constants.EXTRACTED_TEXT,
                criterion_type=constants.CRITERION_TYPE,
                confidence=constants.CRITERION_CONFIDENCE,
            )
        ]

    monkeypatch.setattr(
        api_main_any.extraction_pipeline,
        "extract_criteria_async",
        _extract_criteria_async,
    )


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
                ontology=constants.SNOMED_ONTOLOGY,
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

    def _extract_criteria_stream(_text: str):
        yield from state.extracted

    async def _extract_criteria_async(
        _text: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ):
        _ = session_id  # Unused but required for signature compatibility
        _ = user_id  # Unused but required for signature compatibility
        return state.extracted

    class FakeUmlsClient:
        def __init__(
            self,
            base_url: str | None = None,
            api_key: str | None = None,
            timeout: float | None = None,
        ) -> None:
            _ = base_url
            _ = api_key
            _ = timeout

        def __enter__(self) -> "FakeUmlsClient":
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            traceback: object | None,
        ) -> None:
            self.close()

        def search_snomed(self, _text: str) -> list[FakeGroundingCandidate]:
            return state.candidates

        def close(self) -> None:
            return None

    def _propose_field_mapping(_text: str) -> list[FakeFieldMapping]:
        return state.field_mappings

    monkeypatch.setattr(
        api_main_any.extraction_pipeline, "extract_criteria", _extract_criteria
    )
    monkeypatch.setattr(
        api_main_any.extraction_pipeline,
        "extract_criteria_stream",
        _extract_criteria_stream,
    )
    monkeypatch.setattr(
        api_main_any.extraction_pipeline,
        "extract_criteria_async",
        _extract_criteria_async,
    )
    monkeypatch.setattr(api_main_any.umls_client, "UmlsClient", FakeUmlsClient)
    monkeypatch.setattr(
        api_main_any.umls_client, "propose_field_mapping", _propose_field_mapping
    )
    monkeypatch.setattr(
        ingestion,
        "extract_triplet",
        lambda _text: '{"entity":"age","relation":">=","value":"18","unit":"years"}',
    )

    return state
