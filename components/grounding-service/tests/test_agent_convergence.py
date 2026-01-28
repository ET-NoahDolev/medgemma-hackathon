"""Regression tests for pipeline convergence behavior.

These tests verify that the SAG pipeline completes quickly and reliably,
preventing regression to slow or non-deterministic behavior.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grounding_service.agent import GroundingPipeline
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
                term="Age",
                snippet="Age >= 18",
                relation=">=",
                value="18",
                unit="years",
                is_computed=True,
                computed_expression="floor((today - birthDate) / 365.25)",
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
                snippet="Age >= 18",
                raw_criterion_text="Age 18 years or older",
                criterion_type="inclusion",
                snomed_code="424144002",
                umls_concept="Age",
                umls_id="C0001779",
                relation=">=",
                value="18",
                unit="years",
                computed_as="floor((today - birthDate) / 365.25)",
                confidence=0.9,
            )
        ],
        reasoning="Selected age criterion with computed expression.",
    )


@pytest.mark.asyncio
async def test_grounding_converges_quickly(
    mock_extraction_result, mock_grounding_result, monkeypatch
):
    """Assert that grounding terminates quickly with the SAG pipeline."""
    monkeypatch.setenv("ENABLE_GROUNDING_SEMANTIC_CACHE", "false")

    simple_criteria = [
        "Age 18 years or older",
        "Diagnosed with hypertension",
        "BMI between 18.5 and 30",
        "No prior chemotherapy",
    ]

    mock_extractor = AsyncMock(return_value=mock_extraction_result)
    mock_selector = AsyncMock(return_value=mock_grounding_result)

    pipeline = GroundingPipeline()
    pipeline._get_extractor = MagicMock(return_value=mock_extractor)
    pipeline._get_selector = MagicMock(return_value=mock_selector)

    with patch.object(pipeline, "_search_umls") as mock_search:
        mock_search.return_value = {
            "Age": [
                MagicMock(
                    term="Age",
                    snomed_code="424144002",
                    display="Age",
                    cui="C0001779",
                )
            ]
        }

        for criterion in simple_criteria:
            result = await pipeline.ground(criterion, "inclusion")

            # Check: Should have completed
            assert result is not None
            assert isinstance(result, GroundingResult)
            assert len(result.terms) > 0

        # Verify extractor and selector were called for each criterion
        assert mock_extractor.await_count == len(simple_criteria)
        assert mock_selector.await_count == len(simple_criteria)


@pytest.mark.asyncio
async def test_grounding_within_time_budget(
    mock_extraction_result, mock_grounding_result, monkeypatch
):
    """Assert that grounding completes within time budget."""
    monkeypatch.setenv("ENABLE_GROUNDING_SEMANTIC_CACHE", "false")

    criterion = "Age 18 years or older"

    mock_extractor = AsyncMock(return_value=mock_extraction_result)
    mock_selector = AsyncMock(return_value=mock_grounding_result)

    pipeline = GroundingPipeline()
    pipeline._get_extractor = MagicMock(return_value=mock_extractor)
    pipeline._get_selector = MagicMock(return_value=mock_selector)

    with patch.object(pipeline, "_search_umls") as mock_search:
        mock_search.return_value = {
            "Age": [
                MagicMock(
                    term="Age",
                    snomed_code="424144002",
                    display="Age",
                    cui="C0001779",
                )
            ]
        }

        start = time.time()
        result = await pipeline.ground(criterion, "inclusion")
        elapsed = time.time() - start

        # Mocked call should be very fast
        assert elapsed < 1.0, f"Grounding took {elapsed:.1f}s, max 1s allowed"
        assert result is not None
        assert isinstance(result, GroundingResult)


@pytest.mark.asyncio
async def test_pipeline_uses_exactly_two_llm_calls(
    mock_extraction_result, mock_grounding_result, monkeypatch
):
    """Assert that the SAG pipeline uses exactly 2 LLM calls (extract + select)."""
    monkeypatch.setenv("ENABLE_GROUNDING_SEMANTIC_CACHE", "false")

    mock_extractor = AsyncMock(return_value=mock_extraction_result)
    mock_selector = AsyncMock(return_value=mock_grounding_result)

    pipeline = GroundingPipeline()
    pipeline._get_extractor = MagicMock(return_value=mock_extractor)
    pipeline._get_selector = MagicMock(return_value=mock_selector)

    with patch.object(pipeline, "_search_umls") as mock_search:
        mock_search.return_value = {"Age": []}

        await pipeline.ground("Age 18 years or older", "inclusion")

        # Verify exactly 2 LLM calls: 1 for extraction, 1 for selection
        assert mock_extractor.await_count == 1, "Should call extractor exactly once"
        assert mock_selector.await_count == 1, "Should call selector exactly once"


@pytest.mark.asyncio
async def test_pipeline_no_iteration_loop(
    mock_extraction_result, mock_grounding_result, monkeypatch
):
    """Assert that the pipeline doesn't have iteration loops."""
    monkeypatch.setenv("ENABLE_GROUNDING_SEMANTIC_CACHE", "false")

    # Track call counts to ensure no loops
    extractor_calls = []
    selector_calls = []

    async def tracking_extractor(prompt_vars):
        extractor_calls.append(prompt_vars)
        return mock_extraction_result

    async def tracking_selector(prompt_vars):
        selector_calls.append(prompt_vars)
        return mock_grounding_result

    pipeline = GroundingPipeline()
    pipeline._get_extractor = MagicMock(return_value=tracking_extractor)
    pipeline._get_selector = MagicMock(return_value=tracking_selector)

    with patch.object(pipeline, "_search_umls") as mock_search:
        mock_search.return_value = {"Age": []}

        await pipeline.ground("Age 18 years or older", "inclusion")

        # No loops - exactly one call each
        assert len(extractor_calls) == 1
        assert len(selector_calls) == 1
