"""Tests for grounding pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grounding_service.agent import (
    GroundingAgent,
    GroundingPipeline,
    get_grounding_agent,
)
from grounding_service.schemas import (
    ExtractedTerm,
    GroundedTerm,
    GroundingResult,
    TermExtractionResult,
)


@pytest.fixture
def mock_extraction_result():
    """Mock term extraction result."""
    return TermExtractionResult(
        terms=[
            ExtractedTerm(
                term="Type 2 Diabetes",
                snippet="Type 2 Diabetes",
                relation=None,
                value=None,
                unit=None,
                is_computed=False,
            )
        ],
        logical_operator=None,
    )


@pytest.fixture
def mock_grounding_result():
    """Mock grounding result."""
    return GroundingResult(
        terms=[
            GroundedTerm(
                snippet="Type 2 Diabetes",
                raw_criterion_text="Patient must have Type 2 Diabetes",
                criterion_type="inclusion",
                snomed_code="44054006",
                umls_concept="Type 2 Diabetes Mellitus",
                umls_id="C0011860",
                relation=None,
                value=None,
                confidence=0.9,
            )
        ],
        reasoning="Selected Type 2 Diabetes code from UMLS results.",
    )


@pytest.mark.asyncio
async def test_ground_returns_structured_result(
    mock_extraction_result, mock_grounding_result, monkeypatch
):
    """Test that ground() returns a structured GroundingResult."""
    monkeypatch.setenv("ENABLE_GROUNDING_SEMANTIC_CACHE", "false")

    mock_extractor = AsyncMock(return_value=mock_extraction_result)
    mock_selector = AsyncMock(return_value=mock_grounding_result)

    pipeline = GroundingPipeline()
    pipeline._get_extractor = MagicMock(return_value=mock_extractor)
    pipeline._get_selector = MagicMock(return_value=mock_selector)

    # Mock UMLS search
    with patch.object(pipeline, "_search_umls") as mock_search:
        mock_search.return_value = {
            "Type 2 Diabetes": [
                MagicMock(
                    term="Type 2 Diabetes",
                    snomed_code="44054006",
                    display="Type 2 Diabetes Mellitus",
                    cui="C0011860",
                )
            ]
        }

        result = await pipeline.ground(
            "Patient must have Type 2 Diabetes", "inclusion"
        )

        assert isinstance(result, GroundingResult)
        assert len(result.terms) > 0
        assert result.terms[0].snomed_code == "44054006"


@pytest.mark.asyncio
async def test_ground_fallback_on_invoke_error(monkeypatch):
    """Test that ground() raises errors when extractor fails."""
    monkeypatch.setenv("ENABLE_GROUNDING_SEMANTIC_CACHE", "false")

    async def failing_extractor(*_args, **_kwargs):
        raise ValueError("Extraction failed")

    pipeline = GroundingPipeline()
    pipeline._get_extractor = MagicMock(return_value=failing_extractor)

    with pytest.raises(ValueError, match="Extraction failed"):
        await pipeline.ground("Age >= 18", "inclusion")


@pytest.mark.asyncio
async def test_ground_uses_cache_when_enabled(monkeypatch):
    """Test that ground() uses cache when enabled."""
    cached = GroundingResult(
        terms=[
            GroundedTerm(
                snippet="Hypertension",
                raw_criterion_text="Hypertension",
                criterion_type="inclusion",
                snomed_code="123",
                relation="=",
                value="Hypertension",
                confidence=0.8,
            )
        ],
        reasoning="cached",
    )

    class DummyCache:
        def get(self, _text):
            return cached, 0.99

        def set(self, _text, _result):
            raise AssertionError("Cache set should not be called on hit")

    monkeypatch.setenv("ENABLE_GROUNDING_SEMANTIC_CACHE", "true")
    monkeypatch.setattr("grounding_service.agent.get_grounding_cache", DummyCache)

    pipeline = GroundingPipeline()
    # These shouldn't be called due to cache hit
    pipeline._get_extractor = MagicMock()
    pipeline._get_selector = MagicMock()

    result = await pipeline.ground("Hypertension", "inclusion")
    assert result == cached
    pipeline._get_extractor.assert_not_called()


@pytest.mark.asyncio
async def test_ground_empty_extraction(monkeypatch, mock_grounding_result):
    """Test that ground() handles empty extraction results."""
    monkeypatch.setenv("ENABLE_GROUNDING_SEMANTIC_CACHE", "false")

    empty_extraction = TermExtractionResult(terms=[], logical_operator=None)
    mock_extractor = AsyncMock(return_value=empty_extraction)

    pipeline = GroundingPipeline()
    pipeline._get_extractor = MagicMock(return_value=mock_extractor)

    result = await pipeline.ground("No clinical terms here", "inclusion")

    assert isinstance(result, GroundingResult)
    assert len(result.terms) == 0
    assert "No clinical terms" in result.reasoning


def test_get_grounding_agent_singleton():
    """Test that get_grounding_agent returns a singleton."""
    import grounding_service.agent

    grounding_service.agent._pipeline_instance = None

    agent1 = get_grounding_agent()
    agent2 = get_grounding_agent()

    assert agent1 is agent2


def test_grounding_agent_is_alias_for_pipeline():
    """Test that GroundingAgent is an alias for GroundingPipeline."""
    assert GroundingAgent is GroundingPipeline


@pytest.mark.asyncio
async def test_search_umls_returns_candidates(monkeypatch):
    """Test that _search_umls returns UMLS candidates."""
    from grounding_service.umls_client import SnomedCandidate

    monkeypatch.setenv("UMLS_API_KEY", "test-key")

    mock_candidate = SnomedCandidate(
        code="44054006",
        display="Type 2 Diabetes Mellitus",
        cui="C0011860",
        ontology="SNOMEDCT_US",
        confidence=0.95,
    )

    with patch("grounding_service.agent.UmlsClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.search_snomed.return_value = [mock_candidate]
        mock_client_class.return_value = mock_client

        pipeline = GroundingPipeline()
        terms = [
            ExtractedTerm(
                term="Type 2 Diabetes",
                snippet="Type 2 Diabetes",
            )
        ]

        results = pipeline._search_umls(terms)

        assert "Type 2 Diabetes" in results
        assert len(results["Type 2 Diabetes"]) == 1
        assert results["Type 2 Diabetes"][0].snomed_code == "44054006"


@pytest.mark.asyncio
async def test_ground_batch(mock_extraction_result, mock_grounding_result, monkeypatch):
    """Test that ground_batch processes multiple criteria."""
    monkeypatch.setenv("ENABLE_GROUNDING_SEMANTIC_CACHE", "false")

    mock_extractor = AsyncMock(return_value=mock_extraction_result)
    mock_selector = AsyncMock(return_value=mock_grounding_result)

    pipeline = GroundingPipeline()
    pipeline._get_extractor = MagicMock(return_value=mock_extractor)
    pipeline._get_selector = MagicMock(return_value=mock_selector)

    with patch.object(pipeline, "_search_umls") as mock_search:
        mock_search.return_value = {
            "Type 2 Diabetes": [
                MagicMock(
                    term="Type 2 Diabetes",
                    snomed_code="44054006",
                    display="Type 2 Diabetes Mellitus",
                    cui="C0011860",
                )
            ]
        }

        items = [
            {
                "criterion_text": "Patient must have Type 2 Diabetes",
                "criterion_type": "inclusion",
            },
            {
                "criterion_text": "No hypertension",
                "criterion_type": "exclusion",
            },
        ]

        results = await pipeline.ground_batch(items)

        assert len(results) == 2
        assert all(isinstance(r, GroundingResult) for r in results)
