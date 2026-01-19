from unittest.mock import MagicMock, patch

import httpx
import pytest

from grounding_service.umls_client import SnomedCandidate, UmlsClient


@pytest.fixture
def mock_umls_success() -> dict[str, object]:
    return {
        "result": {
            "results": [
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
        }
    }


class TestUmlsClientSearch:
    def test_search_snomed_returns_candidates(
        self,
        mock_umls_success: dict[str, object],
    ) -> None:
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = MagicMock(
                json=lambda: mock_umls_success,
                status_code=200,
                raise_for_status=lambda: None,
            )
            mock_client_cls.return_value = mock_client
            client = UmlsClient(api_key="test-key")
            candidates = client.search_snomed("melanoma")

        assert len(candidates) == 2
        assert isinstance(candidates[0], SnomedCandidate)

    def test_search_snomed_maps_fields(
        self,
        mock_umls_success: dict[str, object],
    ) -> None:
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = MagicMock(
                json=lambda: mock_umls_success,
                status_code=200,
                raise_for_status=lambda: None,
            )
            mock_client_cls.return_value = mock_client
            client = UmlsClient(api_key="test-key")
            candidates = client.search_snomed("melanoma")

        assert candidates[0].code == "372244006"
        assert candidates[0].display == "Malignant melanoma, stage III"
        assert candidates[0].ontology == "SNOMEDCT_US"

    def test_search_snomed_caches_results(
        self,
        mock_umls_success: dict[str, object],
    ) -> None:
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = MagicMock(
                json=lambda: mock_umls_success,
                status_code=200,
                raise_for_status=lambda: None,
            )
            mock_client_cls.return_value = mock_client
            client = UmlsClient(api_key="test-key")
            client.search_snomed("melanoma")
            client.search_snomed("melanoma")

        assert mock_client.get.call_count == 1

    def test_search_snomed_empty_query_raises(self) -> None:
        client = UmlsClient(api_key="test-key")
        with pytest.raises(ValueError, match="query is required"):
            client.search_snomed("")

    def test_search_snomed_missing_api_key_raises(self) -> None:
        with pytest.raises(ValueError, match="UMLS_API_KEY is required"):
            UmlsClient(api_key=None)

    def test_search_snomed_respects_limit(
        self,
        mock_umls_success: dict[str, object],
    ) -> None:
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = MagicMock(
                json=lambda: mock_umls_success,
                status_code=200,
                raise_for_status=lambda: None,
            )
            mock_client_cls.return_value = mock_client
            client = UmlsClient(api_key="test-key")
            candidates = client.search_snomed("melanoma", limit=1)

        assert len(candidates) == 1

    def test_search_snomed_returns_empty_on_timeout(self) -> None:
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.RequestError(
                "Timeout",
                request=MagicMock(),
            )
            mock_client_cls.return_value = mock_client
            client = UmlsClient(api_key="test-key")
            candidates = client.search_snomed("melanoma")

        assert candidates == []


class TestUmlsClientConfig:
    def test_default_base_url(self) -> None:
        client = UmlsClient(api_key="test-key")
        assert "uts-ws" in client.base_url

    def test_custom_base_url(self) -> None:
        client = UmlsClient(base_url="http://localhost:8080", api_key="test-key")
        assert client.base_url == "http://localhost:8080"
