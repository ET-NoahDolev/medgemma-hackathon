import asyncio
import io

import pytest
from extraction_service.pdf_extractor import CriterionSnippet, PDFExtractionResult
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_service import main as api_main
from api_service.storage import Storage, get_engine, reset_storage
from tests.conftest import FakeServicesState
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

# Minimal valid PDF (empty page)
_MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj "
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n"
    b"0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n166\n%%EOF"
)


def _create_protocol_with_criterion(
    client: TestClient,
    text: str = EXTRACTED_TEXT,
    criterion_type: str = CRITERION_TYPE,
    confidence: float = CRITERION_CONFIDENCE,
    snomed_codes: list[str] | None = None,
) -> tuple[str, str]:
    """Create a protocol and criterion directly via storage, bypassing extraction.

    Returns:
        Tuple of (protocol_id, criterion_id).
    """
    reset_storage()
    storage = Storage(get_engine())
    protocol = storage.create_protocol(
        title=PROTOCOL_TITLE,
        document_text=DOCUMENT_TEXT,
    )
    criterion = storage.create_criterion_detail(
        protocol_id=protocol.id,
        text=text,
        criterion_type=criterion_type,
        confidence=confidence,
        entity="age",
        relation=">=",
        value="18",
        unit="years",
        snomed_codes=snomed_codes or [SNOMED_CODE],
    )
    return protocol.id, criterion.id


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


def test_extract_criteria_requires_pdf(
    client: TestClient,
    fake_services: FakeServicesState,
) -> None:
    """Test that extraction fails for protocols without PDF bytes."""
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]

    extract_response = client.post(f"/v1/protocols/{protocol_id}/extract")
    assert extract_response.status_code == 400
    assert "PDF" in extract_response.json()["detail"]


def test_extract_criteria_with_pdf_upload(
    client: TestClient,
    fake_services: FakeServicesState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test extraction workflow using PDF upload."""

    async def mock_extract_criteria_from_pdf(**kwargs: object) -> object:
        return PDFExtractionResult(
            criteria=[
                CriterionSnippet(
                    text=EXTRACTED_TEXT,
                    criterion_type=CRITERION_TYPE,
                    confidence=CRITERION_CONFIDENCE,
                )
            ]
        )

    def mock_extract_triplets_batch(texts: list[str]) -> list[dict[str, str | None]]:
        return [{"entity": "age", "relation": ">=", "value": "18", "unit": "years"}]

    monkeypatch.setattr(
        "api_service.ingestion.extract_criteria_from_pdf",
        mock_extract_criteria_from_pdf,
    )
    monkeypatch.setattr(
        "api_service.ingestion.extract_triplets_batch",
        mock_extract_triplets_batch,
    )

    upload_response = client.post(
        "/v1/protocols/upload",
        files={"file": ("test.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf")},
        params={"auto_extract": "false"},
    )
    assert upload_response.status_code == 200
    protocol_id = upload_response.json()["protocol_id"]

    extract_response = client.post(f"/v1/protocols/{protocol_id}/extract")
    assert extract_response.status_code == 200
    assert extract_response.json()["status"] == "processing"

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["protocol_id"] == protocol_id
    assert len(payload["criteria"]) == 1

    criterion = payload["criteria"][0]
    assert criterion["text"] == EXTRACTED_TEXT
    assert criterion["criterion_type"] == CRITERION_TYPE
    assert criterion["snomed_codes"] == [SNOMED_CODE]


def test_update_criterion_returns_updated_value(
    client: TestClient,
    fake_services: FakeServicesState,
) -> None:
    protocol_id, criterion_id = _create_protocol_with_criterion(client)

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
    _, criterion_id = _create_protocol_with_criterion(client)

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
    _, criterion_id = _create_protocol_with_criterion(client)

    response = client.post(
        "/v1/hitl/feedback",
        json={"criterion_id": criterion_id, "action": "accept"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "recorded"}


def test_extract_replaces_existing_criteria(
    client: TestClient,
    fake_services: FakeServicesState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that re-extraction replaces existing criteria."""
    extraction_results: list[list[object]] = []

    async def mock_extract_criteria_from_pdf(**kwargs: object) -> object:
        results = extraction_results.pop(0) if extraction_results else []
        return PDFExtractionResult(criteria=results)

    def mock_extract_triplets_batch(texts: list[str]) -> list[dict[str, str | None]]:
        return [
            {"entity": "age", "relation": ">=", "value": "18", "unit": "years"}
            for _ in texts
        ]

    monkeypatch.setattr(
        "api_service.ingestion.extract_criteria_from_pdf",
        mock_extract_criteria_from_pdf,
    )
    monkeypatch.setattr(
        "api_service.ingestion.extract_triplets_batch",
        mock_extract_triplets_batch,
    )

    # First extraction returns one criterion
    extraction_results.append([
        CriterionSnippet(text="Age >= 18", criterion_type="inclusion", confidence=0.9)
    ])
    # Second extraction returns two criteria
    extraction_results.append([
        CriterionSnippet(text="Age >= 21", criterion_type="inclusion", confidence=0.91),
        CriterionSnippet(text="BMI < 30", criterion_type="inclusion", confidence=0.75),
    ])

    upload_response = client.post(
        "/v1/protocols/upload",
        files={"file": ("test.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf")},
        params={"auto_extract": "false"},
    )
    protocol_id = upload_response.json()["protocol_id"]

    first_extract = client.post(f"/v1/protocols/{protocol_id}/extract")
    assert first_extract.status_code == 200

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    assert len(list_response.json()["criteria"]) == 1

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
    _, criterion_id = _create_protocol_with_criterion(client)

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
    _, criterion_id = _create_protocol_with_criterion(client)

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
    monkeypatch.setattr(
        "grounding_service.agent.get_grounding_agent",
        lambda: mock_agent,
    )
    monkeypatch.setattr(api_main, "AGENT_AVAILABLE", True)

    _, criterion_id = _create_protocol_with_criterion(client)

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
    monkeypatch.setattr(
        "grounding_service.agent.get_grounding_agent",
        lambda: mock_agent,
    )
    monkeypatch.setattr(api_main, "AGENT_AVAILABLE", True)

    _, criterion_id = _create_protocol_with_criterion(client)

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


def test_criterion_response_includes_umls_mappings_and_logical_operator(
    client: TestClient,
    fake_services: FakeServicesState,
) -> None:
    """Test that CriterionDetailResponse includes umls_mappings and logical_operator."""
    from api_service.storage import Storage, get_engine

    storage = Storage(get_engine())

    # Create a protocol
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]

    # Create a criterion with grounding_terms and logical_operator
    grounding_terms = [
        {
            "umls_concept": "Age",
            "umls_id": "C0001779",
            "snomed_code": "371273006",
            "relation": ">=",
            "value": "18",
            "unit": "years",
            "umls_confidence": 0.95,
            "grounding_confidence": 0.92,
        },
        {
            "umls_concept": "Body weight",
            "umls_id": "C0005910",
            "snomed_code": "27113001",
            "relation": ">=",
            "value": "50",
            "unit": "kg",
            "umls_confidence": 0.88,
            "grounding_confidence": 0.85,
        },
    ]

    storage.create_criterion_detail(
        protocol_id=protocol_id,
        text="Age >= 18 years AND weight >= 50 kg",
        criterion_type="inclusion",
        confidence=0.9,
        entity="age",
        relation=">=",
        value="18",
        unit="years",
        umls_concept="Age",
        umls_id="C0001779",
        snomed_codes=["371273006", "27113001"],
        logical_operator="AND",
        grounding_terms=grounding_terms,
    )

    # Get criteria list and verify response includes new fields
    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    assert list_response.status_code == 200

    criteria = list_response.json()["criteria"]
    assert len(criteria) == 1

    criterion_response = criteria[0]

    # Verify logical_operator is included
    assert "logical_operator" in criterion_response
    assert criterion_response["logical_operator"] == "AND"

    # Verify grounding_terms is included
    assert "grounding_terms" in criterion_response
    assert len(criterion_response["grounding_terms"]) == 2
    assert criterion_response["grounding_terms"][0]["umls_concept"] == "Age"
    assert criterion_response["grounding_terms"][1]["umls_concept"] == "Body weight"

    # Verify umls_mappings is included and derived from grounding_terms
    assert "umls_mappings" in criterion_response
    assert len(criterion_response["umls_mappings"]) == 2

    # Verify first mapping
    mapping1 = criterion_response["umls_mappings"][0]
    assert mapping1["umls_concept"] == "Age"
    assert mapping1["umls_id"] == "C0001779"
    assert mapping1["snomed_code"] == "371273006"
    assert "confidence" in mapping1

    # Verify second mapping
    mapping2 = criterion_response["umls_mappings"][1]
    assert mapping2["umls_concept"] == "Body weight"
    assert mapping2["umls_id"] == "C0005910"
    assert mapping2["snomed_code"] == "27113001"
    assert "confidence" in mapping2


def test_lifespan_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UMLS_API_KEY", raising=False)
    monkeypatch.delenv("GROUNDING_SERVICE_UMLS_API_KEY", raising=False)
    from api_service import main as api_main

    async def _run() -> None:
        async with api_main.lifespan(FastAPI()):
            pass

    with pytest.raises(RuntimeError, match="UMLS_API_KEY"):
        asyncio.run(_run())
