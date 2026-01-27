from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from api_service.ingestion import _ground_with_ai, ingest_protocol_document_text
from api_service.storage import Storage, get_engine


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


@pytest.mark.asyncio
async def test_ingestion_pipeline_stores_triplet_and_grounding(
    monkeypatch: pytest.MonkeyPatch,
    fake_services,
) -> None:
    storage = Storage(get_engine())

    def _extract_criteria_stream(_text: str):
        yield from fake_services.extracted

    async def _extract_criteria_async(
        _text: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ):
        _ = session_id  # Unused but required for signature compatibility
        _ = user_id  # Unused but required for signature compatibility
        return fake_services.extracted

    class FakeUmlsClient:
        def __init__(self, *args, **kwargs) -> None:
            _ = args
            _ = kwargs

        def __enter__(self) -> "FakeUmlsClient":
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def search_snomed(self, _text: str):
            return [
                FakeGroundingCandidate(
                    code="371273006",
                    display="Age (finding)",
                    ontology="SNOMEDCT_US",
                    confidence=0.88,
                )
            ]

    def _propose_field_mapping(_text: str):
        return [
            FakeFieldMapping(
                field="demographics.age",
                relation=">=",
                value="18",
                confidence=0.77,
            )
        ]

    monkeypatch.setattr(
        "api_service.ingestion.extraction_pipeline.extract_criteria_stream",
        _extract_criteria_stream,
    )
    monkeypatch.setattr(
        "api_service.ingestion.extraction_pipeline.extract_criteria_async",
        _extract_criteria_async,
    )
    monkeypatch.setattr("api_service.ingestion.umls_client.UmlsClient", FakeUmlsClient)
    monkeypatch.setattr(
        "api_service.ingestion.umls_client.propose_field_mapping",
        _propose_field_mapping,
    )
    monkeypatch.setattr(
        "api_service.ingestion.extract_triplet",
        lambda _text: '{"entity":"age","relation":">=","value":"18","unit":"years"}',
    )

    stored = await ingest_protocol_document_text(
        protocol_id="proto-1",
        document_text="Inclusion: Age >= 18 years.",
        storage=storage,
        umls_api_key="test-key",
    )

    assert len(stored) == 1
    criterion = stored[0]
    assert criterion.entity == "age"
    assert criterion.relation == ">="
    assert criterion.value == "18"
    assert criterion.unit == "years"
    assert criterion.snomed_codes == ["371273006"]


@pytest.mark.asyncio
async def test_ground_with_ai_returns_all_terms_and_logical_operator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _ground_with_ai returns tuple with terms and logical operator."""
    # Create mock grounded terms
    mock_term1 = MagicMock()
    mock_term1.umls_concept = "Age"
    mock_term1.umls_id = "C0001779"
    mock_term1.snomed_code = "371273006"
    mock_term1.relation = ">="
    mock_term1.value = "18"
    mock_term1.unit = "years"
    mock_term1.computed_as = None
    mock_term1.confidence = 0.95
    mock_term1.relation_confidence = 0.9
    mock_term1.value_confidence = 0.85
    mock_term1.umls_confidence = 0.92
    mock_term1.snippet = "Age >= 18 years"

    mock_term2 = MagicMock()
    mock_term2.umls_concept = "Body weight"
    mock_term2.umls_id = "C0005910"
    mock_term2.snomed_code = "27113001"
    mock_term2.relation = ">="
    mock_term2.value = "50"
    mock_term2.unit = "kg"
    mock_term2.computed_as = None
    mock_term2.confidence = 0.88
    mock_term2.relation_confidence = 0.87
    mock_term2.value_confidence = 0.86
    mock_term2.umls_confidence = 0.89
    mock_term2.snippet = "weight >= 50 kg"

    # Create mock GroundingResult
    mock_result = MagicMock()
    mock_result.terms = [mock_term1, mock_term2]
    mock_result.logical_operator = "AND"

    # Mock the grounding agent
    mock_agent = AsyncMock()
    mock_agent.ground = AsyncMock(return_value=mock_result)

    def mock_get_grounding_agent():
        return mock_agent

    monkeypatch.setattr(
        "grounding_service.agent.get_grounding_agent",
        mock_get_grounding_agent,
    )

    # Call _ground_with_ai
    primary_dict, snomed_codes, grounding_terms, logical_operator = (
        await _ground_with_ai("Age >= 18 years AND weight >= 50 kg", "inclusion")
    )

    # Verify return signature
    assert isinstance(primary_dict, dict)
    assert isinstance(snomed_codes, list)
    assert isinstance(grounding_terms, list)
    assert logical_operator == "AND"

    # Verify primary term (first term)
    assert primary_dict["umls_concept"] == "Age"
    assert primary_dict["umls_id"] == "C0001779"
    assert primary_dict["snomed_code"] == "371273006"

    # Verify SNOMED codes list
    assert len(snomed_codes) == 2
    assert "371273006" in snomed_codes
    assert "27113001" in snomed_codes

    # Verify all grounding terms
    assert len(grounding_terms) == 2
    assert grounding_terms[0]["umls_concept"] == "Age"
    assert grounding_terms[0]["snomed_code"] == "371273006"
    assert grounding_terms[0]["snippet"] == "Age >= 18 years"
    assert grounding_terms[1]["umls_concept"] == "Body weight"
    assert grounding_terms[1]["snomed_code"] == "27113001"
    assert grounding_terms[1]["snippet"] == "weight >= 50 kg"

    # Verify logical operator
    assert logical_operator == "AND"


@pytest.mark.asyncio
async def test_ground_with_ai_returns_none_when_no_terms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that _ground_with_ai returns empty results when agent returns no terms."""
    # Create mock GroundingResult with no terms
    mock_result = MagicMock()
    mock_result.terms = []

    # Mock the grounding agent
    mock_agent = AsyncMock()
    mock_agent.ground = AsyncMock(return_value=mock_result)

    def mock_get_grounding_agent():
        return mock_agent

    # Patch at the import location
    monkeypatch.setattr(
        "grounding_service.agent.get_grounding_agent",
        mock_get_grounding_agent,
    )

    # Call _ground_with_ai (it imports get_grounding_agent inside the function)
    import api_service.ingestion as ingestion_module

    primary_dict, snomed_codes, grounding_terms, logical_operator = (
        await ingestion_module._ground_with_ai("Some text", "inclusion")
    )

    # Verify empty results
    assert primary_dict == {}
    assert snomed_codes == []
    assert grounding_terms == []
    assert logical_operator is None
