from collections.abc import Callable
from unittest.mock import MagicMock, patch

import httpx
import pytest

from grounding_service.umls_client import (
    SnomedCandidate,
    UmlsApiAuthenticationError,
    UmlsApiClientError,
    UmlsApiError,
    UmlsApiRateLimitError,
    UmlsApiServerError,
    UmlsClient,
    _ServerError,
)


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


class TestUmlsClientExceptionHierarchy:
    """Test UMLS client exception hierarchy and error handling."""

    def test_authentication_error_401(self) -> None:
        """Test that 401 status code raises UmlsApiAuthenticationError."""
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_response.is_success = False
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "401 Unauthorized", request=MagicMock(), response=mock_response
                )
            )
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            with UmlsClient(api_key="test-key") as client:
                with pytest.raises(UmlsApiAuthenticationError) as exc_info:
                    client.search_snomed("test")

        assert exc_info.value.status_code == 401
        assert "Authentication failed" in exc_info.value.message
        assert exc_info.value.response_body == "Unauthorized"

    def test_authentication_error_403(self) -> None:
        """Test that 403 status code raises UmlsApiAuthenticationError."""
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.text = "Forbidden"
            mock_response.is_success = False
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "403 Forbidden", request=MagicMock(), response=mock_response
                )
            )
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            with UmlsClient(api_key="test-key") as client:
                with pytest.raises(UmlsApiAuthenticationError) as exc_info:
                    client.search_snomed("test")

        assert exc_info.value.status_code == 403
        assert "Authentication failed" in exc_info.value.message

    def test_rate_limit_error_429(self) -> None:
        """Test that 429 status code raises UmlsApiRateLimitError."""
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.text = "Too Many Requests"
            mock_response.is_success = False
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "429 Too Many Requests", request=MagicMock(), response=mock_response
                )
            )
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            with UmlsClient(api_key="test-key") as client:
                with pytest.raises(UmlsApiRateLimitError) as exc_info:
                    client.search_snomed("test")

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.message
        assert exc_info.value.response_body == "Too Many Requests"

    def test_server_error_500(self) -> None:
        """Test that 500 status code raises _ServerError after retries."""
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.is_success = False
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "500 Internal Server Error",
                    request=MagicMock(),
                    response=mock_response,
                )
            )
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            with UmlsClient(api_key="test-key") as client:
                # After retries are exhausted, _ServerError is raised
                with pytest.raises(_ServerError) as exc_info:
                    client.search_snomed("test")

        assert exc_info.value.status_code == 500
        assert "Internal Server Error" in exc_info.value.body

    def test_server_error_503(self) -> None:
        """Test that 503 status code raises _ServerError after retries."""
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_response.text = "Service Unavailable"
            mock_response.is_success = False
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "503 Service Unavailable",
                    request=MagicMock(),
                    response=mock_response,
                )
            )
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            with UmlsClient(api_key="test-key") as client:
                # After retries are exhausted, _ServerError is raised
                with pytest.raises(_ServerError) as exc_info:
                    client.search_snomed("test")

        assert exc_info.value.status_code == 503
        assert "Service Unavailable" in exc_info.value.body

    def test_exception_hierarchy_inheritance(self) -> None:
        """Test that exception hierarchy is correct."""
        # AuthenticationError should inherit from ClientError
        assert issubclass(UmlsApiAuthenticationError, UmlsApiClientError)
        # RateLimitError should inherit from ClientError
        assert issubclass(UmlsApiRateLimitError, UmlsApiClientError)
        # All should inherit from base UmlsApiError
        assert issubclass(UmlsApiAuthenticationError, UmlsApiClientError)
        assert issubclass(UmlsApiRateLimitError, UmlsApiClientError)
        assert issubclass(UmlsApiServerError, UmlsApiError)
