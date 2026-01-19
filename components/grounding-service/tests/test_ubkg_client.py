from unittest.mock import MagicMock, patch

import pytest

from grounding_service.ubkg_client import UbkgCandidate, UbkgClient


@pytest.fixture
def mock_ubkg_success() -> list[dict[str, str]]:
    return [
        {
            "ui": "372244006",
            "name": "Malignant melanoma, stage III",
            "rootSource": "SNOMEDCT_US",
        },
        {
            "ui": "363346000",
            "name": "Malignant neoplastic disease",
            "rootSource": "SNOMEDCT_US",
        },
    ]


class TestUbkgClientSearch:
    def test_search_snomed_returns_candidates(self, mock_ubkg_success: list[dict[str, str]]) -> None:
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_ubkg_success,
                status_code=200,
                raise_for_status=lambda: None,
            )
            client = UbkgClient()
            candidates = client.search_snomed("melanoma")

        assert len(candidates) == 2
        assert isinstance(candidates[0], UbkgCandidate)

    def test_search_snomed_maps_fields(self, mock_ubkg_success: list[dict[str, str]]) -> None:
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_ubkg_success,
                status_code=200,
                raise_for_status=lambda: None,
            )
            client = UbkgClient()
            candidates = client.search_snomed("melanoma")

        assert candidates[0].code == "372244006"
        assert candidates[0].display == "Malignant melanoma, stage III"
        assert candidates[0].ontology == "SNOMED CT"

    def test_search_snomed_caches_results(self, mock_ubkg_success: list[dict[str, str]]) -> None:
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_ubkg_success,
                status_code=200,
                raise_for_status=lambda: None,
            )
            client = UbkgClient()
            client.search_snomed("melanoma")
            client.search_snomed("melanoma")

        assert mock_get.call_count == 1

    def test_search_snomed_empty_query_raises(self) -> None:
        client = UbkgClient()
        with pytest.raises(ValueError, match="query is required"):
            client.search_snomed("")

    def test_search_snomed_respects_limit(self, mock_ubkg_success: list[dict[str, str]]) -> None:
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_ubkg_success,
                status_code=200,
                raise_for_status=lambda: None,
            )
            client = UbkgClient()
            candidates = client.search_snomed("melanoma", limit=1)

        assert len(candidates) == 1

    def test_search_snomed_fallback_on_timeout(self) -> None:
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = Exception("Timeout")
            client = UbkgClient()
            candidates = client.search_snomed("melanoma")

        assert isinstance(candidates, list)


class TestUbkgClientConfig:
    def test_default_base_url(self) -> None:
        client = UbkgClient()
        assert "ubkg-api" in client.base_url

    def test_custom_base_url(self) -> None:
        client = UbkgClient(base_url="http://localhost:8080")
        assert client.base_url == "http://localhost:8080"
