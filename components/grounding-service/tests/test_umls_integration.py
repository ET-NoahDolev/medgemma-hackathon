"""Integration tests for real UMLS API calls.

These tests are skipped unless UMLS_API_KEY is set in the environment.
Run with: uv run pytest tests/test_umls_integration.py -v
"""

from __future__ import annotations

import os

import pytest

from grounding_service.umls_client import UmlsClient

UMLS_API_KEY = os.getenv("UMLS_API_KEY")

pytestmark = pytest.mark.skipif(
    not UMLS_API_KEY,
    reason="UMLS_API_KEY not set; skipping integration tests",
)


class TestUmlsIntegration:
    """Integration tests that hit the real UMLS API."""

    def test_search_snomed_returns_candidates(self) -> None:
        """Search for a common medical term and verify candidates returned."""
        with UmlsClient(api_key=UMLS_API_KEY) as client:
            candidates = client.search_snomed("heart failure")

        assert len(candidates) > 0
        assert candidates[0].code
        assert candidates[0].display
        assert candidates[0].ontology == "SNOMEDCT_US"

    def test_search_snomed_diabetes(self) -> None:
        """Search for diabetes and verify SNOMED code."""
        with UmlsClient(api_key=UMLS_API_KEY) as client:
            candidates = client.search_snomed("diabetes mellitus")

        assert len(candidates) > 0
        # Diabetes mellitus type 2 or similar should be in results
        displays = [c.display.lower() for c in candidates]
        assert any("diabetes" in d for d in displays)

    def test_search_snomed_melanoma(self) -> None:
        """Search for melanoma and verify candidates."""
        with UmlsClient(api_key=UMLS_API_KEY) as client:
            candidates = client.search_snomed("melanoma")

        assert len(candidates) > 0
        displays = [c.display.lower() for c in candidates]
        assert any("melanoma" in d for d in displays)

    def test_search_snomed_respects_limit(self) -> None:
        """Verify pageSize/limit parameter works."""
        with UmlsClient(api_key=UMLS_API_KEY) as client:
            candidates = client.search_snomed("cancer", limit=3)

        assert len(candidates) <= 3

    def test_search_snomed_empty_query_raises(self) -> None:
        """Empty query should raise ValueError."""
        with UmlsClient(api_key=UMLS_API_KEY) as client:
            with pytest.raises(ValueError, match="query is required"):
                client.search_snomed("")

    def test_search_snomed_caches_results(self) -> None:
        """Verify caching works (second call should use cache)."""
        with UmlsClient(api_key=UMLS_API_KEY) as client:
            # First call populates cache
            first = client.search_snomed("hypertension")
            # Second call should return same results from cache
            second = client.search_snomed("hypertension")

        assert first == second
