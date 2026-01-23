from collections.abc import Callable
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


def _create_mock_response_handler(
    search_response: dict[str, object],
    atoms_responses: dict[str, dict[str, object]],
) -> Callable[..., MagicMock]:
    """Create a mock response handler that returns different responses based on URL."""
    def _handler(*args: object, **kwargs: object) -> MagicMock:
        # httpx.Client.get(url, params=...) - url is first positional arg
        url = str(args[0]) if args else ""
        if "/search/current" in url:
            return MagicMock(
                json=lambda: search_response,
                status_code=200,
                raise_for_status=lambda: None,
            )
        elif "/atoms" in url:
            # Extract CUI from URL
            for cui, atoms_response in atoms_responses.items():
                if f"/CUI/{cui}/atoms" in url:
                    return MagicMock(
                        json=lambda: atoms_response,
                        status_code=200,
                        raise_for_status=lambda: None,
                    )
            # Default atoms response if CUI not found
            return MagicMock(
                json=lambda: {"result": {"results": [{"code": ""}]}},
                status_code=200,
                raise_for_status=lambda: None,
            )
        # Default response
        return MagicMock(
            json=lambda: search_response,
            status_code=200,
            raise_for_status=lambda: None,
        )
    return _handler


class TestUmlsClientSearch:
    def test_search_snomed_returns_candidates(
        self,
        mock_umls_success: dict[str, object],
    ) -> None:
        atoms_responses = {
            "372244006": {"result": {"results": [{"code": "372244006"}]}},
            "363346000": {"result": {"results": [{"code": "363346000"}]}},
        }
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.side_effect = _create_mock_response_handler(
                mock_umls_success, atoms_responses
            )
            mock_client_cls.return_value = mock_client
            with UmlsClient(api_key="test-key") as client:
                candidates = client.search_snomed("melanoma")

        assert len(candidates) == 2
        assert isinstance(candidates[0], SnomedCandidate)

    def test_search_snomed_maps_fields(
        self,
        mock_umls_success: dict[str, object],
    ) -> None:
        atoms_responses = {
            "372244006": {"result": {"results": [{"code": "372244006"}]}},
            "363346000": {"result": {"results": [{"code": "363346000"}]}},
        }
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.side_effect = _create_mock_response_handler(
                mock_umls_success, atoms_responses
            )
            mock_client_cls.return_value = mock_client
            with UmlsClient(api_key="test-key") as client:
                candidates = client.search_snomed("melanoma")

        assert candidates[0].code == "372244006"
        assert candidates[0].display == "Malignant melanoma, stage III"
        assert candidates[0].ontology == "SNOMEDCT_US"

    def test_search_snomed_caches_results(
        self,
        mock_umls_success: dict[str, object],
    ) -> None:
        atoms_responses = {
            "372244006": {"result": {"results": [{"code": "372244006"}]}},
            "363346000": {"result": {"results": [{"code": "363346000"}]}},
        }
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.side_effect = _create_mock_response_handler(
                mock_umls_success, atoms_responses
            )
            mock_client_cls.return_value = mock_client
            with UmlsClient(api_key="test-key") as client:
                client.search_snomed("melanoma")
                client.search_snomed("melanoma")

        # First call: 1 search + 2 atoms (one per candidate)
        # Second call: cached, so 0 calls
        # Total: 3 calls (1 search + 2 atoms)
        assert mock_client.get.call_count == 3

    def test_search_snomed_empty_query_raises(self) -> None:
        with UmlsClient(api_key="test-key") as client:
            with pytest.raises(ValueError, match="query is required"):
                client.search_snomed("")

    def test_search_snomed_missing_api_key_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("UMLS_API_KEY", raising=False)
        with pytest.raises(ValueError, match="UMLS_API_KEY is required"):
            UmlsClient(api_key=None)

    def test_search_snomed_respects_limit(
        self,
        mock_umls_success: dict[str, object],
    ) -> None:
        atoms_responses = {
            "372244006": {"result": {"results": [{"code": "372244006"}]}},
        }
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.side_effect = _create_mock_response_handler(
                mock_umls_success, atoms_responses
            )
            mock_client_cls.return_value = mock_client
            with UmlsClient(api_key="test-key") as client:
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
            with UmlsClient(api_key="test-key") as client:
                candidates = client.search_snomed("melanoma")

        assert candidates == []


class TestUmlsClientConfig:
    def test_default_base_url(self) -> None:
        with UmlsClient(api_key="test-key") as client:
            assert "uts-ws" in client.base_url

    def test_custom_base_url(self) -> None:
        with UmlsClient(base_url="http://localhost:8080", api_key="test-key") as client:
            assert client.base_url == "http://localhost:8080"
