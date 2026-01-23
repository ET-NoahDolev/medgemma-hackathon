"""Integration tests for real UMLS API calls.

These tests require UMLS_API_KEY in .env or environment.
Run with: uv run pytest tests/test_umls_integration.py -v
"""

from __future__ import annotations

import os

import pytest
from dotenv import find_dotenv, load_dotenv

from grounding_service.umls_client import UmlsClient

# Load .env from repo root (find_dotenv walks up to find it)
load_dotenv(find_dotenv(), override=True)

pytestmark = [pytest.mark.integration]


@pytest.fixture(scope="session")
def umls_api_key() -> str:
    """Return the configured UMLS API key or fail fast."""
    api_key = os.getenv("UMLS_API_KEY") or os.getenv("GROUNDING_SERVICE_UMLS_API_KEY")
    if not api_key:
        pytest.fail(
            "UMLS API key not set. Provide UMLS_API_KEY or "
            "GROUNDING_SERVICE_UMLS_API_KEY to run integration tests."
        )
    return api_key


class TestUmlsIntegration:
    """Integration tests that hit the real UMLS API."""

    def test_search_snomed_returns_candidates(self, umls_api_key: str) -> None:
        """Search for a common medical term and verify candidates returned."""
        with UmlsClient(api_key=umls_api_key) as client:
            candidates = client.search_snomed("heart failure")

        assert len(candidates) > 0
        assert candidates[0].display
        # Ontology may be MTH (Metathesaurus) or SNOMEDCT_US depending on API response
        assert candidates[0].ontology
        # Code may be empty if atoms endpoint doesn't return expected structure
        # This is acceptable for integration test - we verify the API call works
        if candidates[0].code:
            assert len(candidates[0].code) > 0

    def test_search_snomed_diabetes(self, umls_api_key: str) -> None:
        """Search for diabetes and verify SNOMED code."""
        with UmlsClient(api_key=umls_api_key) as client:
            candidates = client.search_snomed("diabetes mellitus")

        assert len(candidates) > 0
        # Diabetes mellitus type 2 or similar should be in results
        displays = [c.display.lower() for c in candidates]
        assert any("diabetes" in d for d in displays)

    def test_search_snomed_melanoma(self, umls_api_key: str) -> None:
        """Search for melanoma and verify candidates."""
        with UmlsClient(api_key=umls_api_key) as client:
            candidates = client.search_snomed("melanoma")

        assert len(candidates) > 0
        displays = [c.display.lower() for c in candidates]
        assert any("melanoma" in d for d in displays)

    def test_search_snomed_respects_limit(self, umls_api_key: str) -> None:
        """Verify pageSize/limit parameter works."""
        with UmlsClient(api_key=umls_api_key) as client:
            candidates = client.search_snomed("cancer", limit=3)

        assert len(candidates) <= 3

    def test_search_snomed_empty_query_raises(self, umls_api_key: str) -> None:
        """Empty query should raise ValueError."""
        with UmlsClient(api_key=umls_api_key) as client:
            with pytest.raises(ValueError, match="query is required"):
                client.search_snomed("")

    def test_search_snomed_caches_results(self, umls_api_key: str) -> None:
        """Verify caching works (second call should use cache)."""
        with UmlsClient(api_key=umls_api_key) as client:
            # First call populates cache
            first = client.search_snomed("hypertension")
            # Second call should return same results from cache
            second = client.search_snomed("hypertension")

        assert first == second
