import asyncio
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_service import main as api_main
from tests.conftest import FakeExtractedCriterion, FakeServicesState
from tests.constants import (
    CRITERION_CONFIDENCE,
    CRITERION_TYPE,
    DOCUMENT_TEXT,
    EXTRACTED_TEXT,
    FIELD_MAPPING_FIELD,
    PROTOCOL_TITLE,
    SNOMED_CODE,
    SNOMED_ONTOLOGY,
)


def test_create_protocol_validation_error(
    client: TestClient,
    fake_services: FakeServicesState,
) -> None:
    response = client.post("/v1/protocols", json={"title": PROTOCOL_TITLE})

    assert response.status_code == 422


def test_upload_rejects_non_pdf_content_type(
    client: TestClient,
    fake_services: FakeServicesState,
) -> None:
    content = io.BytesIO(b"%PDF-1.4\n")
    response = client.post(
        "/v1/protocols/upload",
        files={"file": ("protocol.pdf", content, "text/plain")},
    )

    assert response.status_code == 415


def test_upload_rejects_invalid_pdf_signature(
    client: TestClient,
    fake_services: FakeServicesState,
) -> None:
    content = io.BytesIO(b"NOPE not a pdf")
    response = client.post(
        "/v1/protocols/upload",
        files={"file": ("protocol.pdf", content, "application/pdf")},
    )

    assert response.status_code == 400


def test_upload_rejects_oversized_file(
    client: TestClient,
    fake_services: FakeServicesState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_main, "MAX_UPLOAD_SIZE_BYTES", 10)
    content = io.BytesIO(b"%PDF" + b"x" * 20)
    response = client.post(
        "/v1/protocols/upload",
        files={"file": ("protocol.pdf", content, "application/pdf")},
    )

    assert response.status_code == 413


def test_extract_criteria_populates_list(
    client: TestClient,
    fake_services: FakeServicesState,
) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]

    extract_response = client.post(f"/v1/protocols/{protocol_id}/extract")
    assert extract_response.status_code == 200
    # Extraction now runs in background, so status is "processing"
    assert extract_response.json()["status"] == "processing"

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    assert list_response.status_code == 200

    payload = list_response.json()
    assert payload["protocol_id"] == protocol_id
    assert len(payload["criteria"]) == 1

    criterion = payload["criteria"][0]
    assert criterion["text"] == EXTRACTED_TEXT
    assert criterion["criterion_type"] == CRITERION_TYPE
    assert criterion["confidence"] == CRITERION_CONFIDENCE
    assert criterion["snomed_codes"] == [SNOMED_CODE]


def test_update_criterion_returns_updated_value(
    client: TestClient,
    fake_services: FakeServicesState,
) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]
    client.post(f"/v1/protocols/{protocol_id}/extract")

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    criterion_id = list_response.json()["criteria"][0]["id"]

    response = client.patch(
        f"/v1/criteria/{criterion_id}",
        json={"text": "Age >= 21", "criterion_type": CRITERION_TYPE},
    )

    assert response.status_code == 200
    assert response.json()["criterion"]["text"] == "Age >= 21"


def test_ground_criterion_returns_candidates(
    client: TestClient,
    fake_services: FakeServicesState,
) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]
    client.post(f"/v1/protocols/{protocol_id}/extract")

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    criterion_id = list_response.json()["criteria"][0]["id"]

    response = client.post(f"/v1/criteria/{criterion_id}/ground")

    assert response.status_code == 200
    payload = response.json()
    assert payload["criterion_id"] == criterion_id
    assert payload["candidates"][0]["code"] == SNOMED_CODE
    assert payload["candidates"][0]["ontology"] == SNOMED_ONTOLOGY
    assert payload["field_mapping"]["field"] == FIELD_MAPPING_FIELD


def test_hitl_feedback_returns_recorded(
    client: TestClient,
    fake_services: FakeServicesState,
) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]
    client.post(f"/v1/protocols/{protocol_id}/extract")

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    criterion_id = list_response.json()["criteria"][0]["id"]

    response = client.post(
        "/v1/hitl/feedback",
        json={"criterion_id": criterion_id, "action": "accept"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "recorded"}


def test_extract_replaces_existing_criteria(
    client: TestClient,
    fake_services: FakeServicesState,
) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]

    first_extract = client.post(f"/v1/protocols/{protocol_id}/extract")
    assert first_extract.status_code == 200

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    assert len(list_response.json()["criteria"]) == 1

    state = fake_services
    state.extracted = [
        FakeExtractedCriterion(
            text="Age >= 21",
            criterion_type=CRITERION_TYPE,
            confidence=0.91,
        ),
        FakeExtractedCriterion(
            text="BMI < 30",
            criterion_type=CRITERION_TYPE,
            confidence=0.75,
        ),
    ]

    second_extract = client.post(f"/v1/protocols/{protocol_id}/extract")
    assert second_extract.status_code == 200

    updated_list = client.get(f"/v1/protocols/{protocol_id}/criteria")
    payload = updated_list.json()
    assert payload["protocol_id"] == protocol_id
    assert len(payload["criteria"]) == 2


def test_ground_criterion_handles_no_mapping(
    client: TestClient,
    fake_services: FakeServicesState,
) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]
    client.post(f"/v1/protocols/{protocol_id}/extract")

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    criterion_id = list_response.json()["criteria"][0]["id"]

    state = fake_services
    state.field_mappings = []

    response = client.post(f"/v1/criteria/{criterion_id}/ground")
    assert response.status_code == 200
    payload = response.json()
    assert payload["field_mapping"] is None


def test_ground_criterion_returns_empty_candidates(
    client: TestClient,
    fake_services: FakeServicesState,
) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]
    client.post(f"/v1/protocols/{protocol_id}/extract")

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    criterion_id = list_response.json()["criteria"][0]["id"]

    state = fake_services
    state.candidates = []

    response = client.post(f"/v1/criteria/{criterion_id}/ground")
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidates"] == []
    assert payload["field_mapping"] is None


def test_ground_criterion_uses_ai_when_enabled(
    client: TestClient,
    fake_services: FakeServicesState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that AI grounding is used when USE_AI_GROUNDING=true."""
    from unittest.mock import AsyncMock, MagicMock

    from grounding_service.schemas import GroundedTerm, GroundingResult

    # Disable AI grounding during extraction to keep it deterministic.
    monkeypatch.setenv("USE_AI_GROUNDING", "false")
    _ = fake_services  # fixture side-effects (monkeypatching) are required

    # Mock the agent
    mock_agent = MagicMock()
    mock_result = GroundingResult(
        terms=[
            GroundedTerm(
                snippet="Age >= 18",
                    raw_criterion_text="Age >= 18",
                    criterion_type="inclusion",
                snomed_code="123456789",
                relation=">=",
                value="18",
                confidence=0.95,
                umls_id="C123456",
            )
        ],
        reasoning="AI reasoning test",
    )
    mock_agent.ground = AsyncMock(return_value=mock_result)

    # Mock get_grounding_agent to return our mock
    monkeypatch.setattr(api_main, "get_grounding_agent", lambda: mock_agent)
    monkeypatch.setattr(api_main, "AGENT_AVAILABLE", True)

    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]
    client.post(f"/v1/protocols/{protocol_id}/extract")

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    criterion_id = list_response.json()["criteria"][0]["id"]

    # Enable AI grounding only for the grounding endpoint.
    monkeypatch.setenv("USE_AI_GROUNDING", "true")

    response = client.post(f"/v1/criteria/{criterion_id}/ground")

    assert response.status_code == 200
    payload = response.json()
    assert payload["criterion_id"] == criterion_id
    # Verify agent was called
    mock_agent.ground.assert_called_once()
    # We should have returned successfully; baseline fallbacks are tested separately.


def test_ground_criterion_falls_back_when_ai_fails(
    client: TestClient,
    fake_services: FakeServicesState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that grounding falls back to baseline when AI fails."""
    from unittest.mock import AsyncMock, MagicMock

    # Enable AI grounding
    monkeypatch.setenv("USE_AI_GROUNDING", "true")
    _ = fake_services  # fixture side-effects (monkeypatching) are required

    # Mock the agent to raise an exception
    mock_agent = MagicMock()
    mock_agent.ground = AsyncMock(side_effect=Exception("AI model error"))

    monkeypatch.setattr(api_main, "get_grounding_agent", lambda: mock_agent)
    monkeypatch.setattr(api_main, "AGENT_AVAILABLE", True)

    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]
    client.post(f"/v1/protocols/{protocol_id}/extract")

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    criterion_id = list_response.json()["criteria"][0]["id"]

    response = client.post(f"/v1/criteria/{criterion_id}/ground")

    # Should still succeed using baseline
    assert response.status_code == 200
    payload = response.json()
    assert payload["criterion_id"] == criterion_id
    # Should have baseline results
    assert (
        len(payload.get("candidates", [])) > 0
        or payload.get("field_mapping") is not None
    )


def test_lifespan_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UMLS_API_KEY", raising=False)
    monkeypatch.delenv("GROUNDING_SERVICE_UMLS_API_KEY", raising=False)
    from api_service import main as api_main

    async def _run() -> None:
        async with api_main.lifespan(FastAPI()):
            pass

    with pytest.raises(RuntimeError, match="UMLS_API_KEY"):
        asyncio.run(_run())
