"""UMLS SNOMED client with disk cache and retry.

Environment variables:
- GROUNDING_SERVICE_UMLS_API_KEY or UMLS_API_KEY: API key for UMLS (required).
  Checked in that order to match API service configuration.
- UMLS_CACHE_DIR: Directory for disk cache (optional; defaults to
  .cache/umls next to module).
- UMLS_CACHE_TTL_SECONDS: TTL in seconds for cache entries (optional;
  defaults to 7 days; must be >0).
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence, cast

import diskcache  # type: ignore[import-untyped]
import httpx
from platformdirs import user_cache_dir
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

UMLS_DEFAULT_URL = "https://uts-ws.nlm.nih.gov/rest"


def get_umls_api_key() -> str | None:
    """Return UMLS API key. Checks GROUNDING_SERVICE_UMLS_API_KEY then UMLS_API_KEY."""
    return os.getenv("GROUNDING_SERVICE_UMLS_API_KEY") or os.getenv("UMLS_API_KEY")


class UmlsApiError(Exception):
    """Base exception for all UMLS API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        """Initialize UMLS API error.

        Args:
            message: Error message.
            status_code: HTTP status code if applicable.
            response_body: Response body if applicable.
        """
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(self.message)


class UmlsApiClientError(UmlsApiError):
    """4xx errors: client configuration or request issues."""

    pass


class UmlsApiServerError(UmlsApiError):
    """5xx errors: server-side issues, should trigger retry."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        """Initialize UMLS API server error.

        Args:
            message: Error message.
            status_code: HTTP status code.
            response_body: Response body.
        """
        super().__init__(message, status_code, response_body)


class UmlsApiTimeoutError(UmlsApiError):
    """Request timeout errors."""

    pass


class UmlsApiAuthenticationError(UmlsApiClientError):
    """401/403: authentication or authorization failures."""

    pass


class UmlsApiRateLimitError(UmlsApiClientError):
    """429: rate limit exceeded."""

    pass


class _ServerError(Exception):
    """Raised on 5xx errors to trigger tenacity retry."""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Server error {status_code}: {body[:100]}")


@dataclass
class SnomedCandidate:
    """SNOMED candidate returned from UMLS.

    Args:
        cui: UMLS Concept Unique Identifier.
        code: SNOMED concept code.
        display: Human-readable concept name.
        ontology: Ontology label (e.g., SNOMEDCT_US).
        confidence: Confidence or relevance score.
    """

    cui: str
    code: str
    display: str
    ontology: str
    confidence: float


@dataclass
class FieldMappingSuggestion:
    """Field/relation/value mapping suggestion for a criterion."""

    field: str
    relation: str
    value: str
    confidence: float


@dataclass
class UmlsApiResponse:
    """Structured response from UMLS API operations."""

    success: bool
    data: list[SnomedCandidate] | dict[str, Any] | None
    error: dict[str, Any] | None = None

    @classmethod
    def success_response(
        cls, data: list[SnomedCandidate] | dict[str, Any]
    ) -> "UmlsApiResponse":
        """Create a successful response."""
        return cls(success=True, data=data, error=None)

    @classmethod
    def error_response(
        cls,
        error_type: str,
        message: str,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> "UmlsApiResponse":
        """Create an error response."""
        error: dict[str, Any] = {
            "type": error_type,
            "message": message,
            "status_code": status_code,
        }
        if details:
            error["details"] = details
        return cls(success=False, data=None, error=error)


class UmlsClient:
    """Client for UMLS REST search endpoints with caching.

    Args:
        base_url: Base URL for the UMLS REST API.
        api_key: UMLS API key (required).
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """Initialize the UMLS client configuration."""
        self.base_url: str = base_url or os.getenv("UMLS_BASE_URL") or UMLS_DEFAULT_URL
        self.api_key = api_key or get_umls_api_key()
        env_timeout = os.getenv("UMLS_TIMEOUT_SECONDS")
        self.timeout = (
            float(env_timeout)
            if env_timeout
            else (timeout if timeout is not None else 10.0)
        )
        if not self.api_key:
            raise ValueError(
                "UMLS API key is required. Set GROUNDING_SERVICE_UMLS_API_KEY "
                "or UMLS_API_KEY."
            )
        self._http = httpx.Client(timeout=self.timeout)
        cache_dir = os.getenv("UMLS_CACHE_DIR")
        default_cache = Path(user_cache_dir("grounding-service", "gemma")) / "umls"
        cache_path = Path(cache_dir) if cache_dir else default_cache
        cache_path.mkdir(parents=True, exist_ok=True)
        self._cache_dir = str(cache_path)
        self._cache_ttl = self._parse_cache_ttl(os.getenv("UMLS_CACHE_TTL_SECONDS"))
        self._cache = diskcache.Cache(self._cache_dir)

    def __enter__(self) -> "UmlsClient":
        """Enter context manager scope."""
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        """Exit context manager scope and close resources."""
        self.close()

    def search_snomed(self, query: str, limit: int = 5) -> list[SnomedCandidate]:
        """Search SNOMED concepts via UMLS.

        Args:
            query: Free-text clinical concept to search.
            limit: Maximum number of candidates to return.

        Returns:
            A list of candidate SNOMED concepts.

        Raises:
            ValueError: If the query is empty or API key is missing.
            UmlsApiAuthenticationError: If authentication fails (401/403).
            UmlsApiRateLimitError: If rate limit is exceeded (429).
            UmlsApiServerError: If server error occurs (5xx).
        """
        if not query.strip():
            raise ValueError("query is required")

        cache_key = f"snomed:{query.lower()}:{limit}"
        cached = cast(list[SnomedCandidate] | None, self._cache.get(cache_key))
        if cached is not None:
            return cached

        try:
            candidates = self._fetch_from_api(query, limit)
            if self._cache_ttl:
                self._cache.set(cache_key, candidates, expire=self._cache_ttl)
            return candidates
        except (UmlsApiAuthenticationError, UmlsApiRateLimitError, UmlsApiServerError):
            # Re-raise critical errors that callers should handle
            raise
        except UmlsApiClientError as exc:
            # For other client errors, log and return empty list
            # for backward compatibility
            logger.error("UMLS API client error in search_snomed: %s", exc.message)
            return []
        except UmlsApiError as exc:
            # For other API errors, log and return empty list
            logger.warning("UMLS API error in search_snomed: %s", exc.message)
            return []

    def _fetch_from_api(self, query: str, limit: int) -> list[SnomedCandidate]:
        """Execute HTTP request to UMLS API with retry on transient errors."""
        url = f"{self.base_url.rstrip('/')}/search/current"
        is_code_query = bool(re.fullmatch(r"\d+", query.strip()))
        params: dict[str, str | int] = {
            "string": query,
            "sabs": "SNOMEDCT_US",
            "searchType": "exact" if is_code_query else "words",
            "inputType": "sourceUi" if is_code_query else "atom",
            "pageSize": limit,
            "apiKey": self.api_key or "",
        }

        try:
            data = self._request_with_retry(url, params)
            fallback = query if is_code_query else ""
            return self._parse_response(data, limit, fallback_code=fallback)
        except UmlsApiAuthenticationError as exc:
            logger.error("UMLS API authentication error: %s", exc.message)
            raise
        except UmlsApiRateLimitError as exc:
            logger.warning("UMLS API rate limit error: %s", exc.message)
            raise
        except UmlsApiClientError as exc:
            logger.error("UMLS API client error: %s", exc.message)
            raise
        except UmlsApiServerError as exc:
            logger.warning("UMLS API server error: %s", exc.message)
            raise
        except httpx.RequestError as exc:
            logger.warning("UMLS API request error: %s", exc)
            raise UmlsApiError(f"Network request failed: {str(exc)}")

    def _map_http_error(self, response: httpx.Response) -> UmlsApiError:
        """Map HTTP response to appropriate UMLS API exception."""
        status = response.status_code
        body = response.text[:500]  # Limit body size

        if status == 401 or status == 403:
            return UmlsApiAuthenticationError(
                message=f"Authentication failed: {body}",
                status_code=status,
                response_body=body,
            )
        elif status == 429:
            return UmlsApiRateLimitError(
                message=f"Rate limit exceeded: {body}",
                status_code=status,
                response_body=body,
            )
        elif 400 <= status < 500:
            return UmlsApiClientError(
                message=f"Client error {status}: {body}",
                status_code=status,
                response_body=body,
            )
        elif status >= 500:
            return UmlsApiServerError(
                message=f"Server error {status}: {body}",
                status_code=status,
                response_body=body,
            )
        else:
            return UmlsApiError(
                message=f"Unexpected status {status}: {body}",
                status_code=status,
                response_body=body,
            )

    @retry(
        retry=retry_if_exception_type(
            (httpx.RequestError, _ServerError, UmlsApiRateLimitError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        reraise=True,
    )
    def _request_with_retry(
        self, url: str, params: dict[str, str | int]
    ) -> dict[str, object]:
        """Make HTTP request with tenacity retry on transient errors."""
        response = self._http.get(url, params=params)
        if response.status_code >= 500:
            logger.warning(
                "UMLS API %d error, will retry: %s",
                response.status_code,
                response.text[:100],
            )
            raise _ServerError(response.status_code, response.text)
        if response.status_code == 429:
            # Rate limit - raise exception to trigger retry
            error = self._map_http_error(response)
            logger.warning("UMLS API rate limit, will retry: %s", error.message)
            raise UmlsApiRateLimitError(
                error.message, error.status_code, error.response_body
            )
        if not response.is_success:
            # Map other HTTP errors but don't retry (except 429 handled above)
            error = self._map_http_error(response)
            if isinstance(error, (UmlsApiAuthenticationError, UmlsApiClientError)):
                logger.error("UMLS API client error: %s", error.message)
            raise error
        return response.json()  # type: ignore[no-any-return]

    def _parse_response(
        self,
        data: dict[str, object],
        limit: int,
        fallback_code: str = "",
    ) -> list[SnomedCandidate]:
        """Parse UMLS API response into candidates."""
        result = data.get("result", {})
        if not isinstance(result, dict):
            return []
        results = result.get("results", [])
        if not isinstance(results, Sequence):
            return []

        candidates: list[SnomedCandidate] = []
        for item in results[:limit]:
            if not isinstance(item, dict):
                continue
            ui = item.get("ui")
            name = item.get("name")
            root = item.get("rootSource")
            cui = str(ui) if isinstance(ui, str) else ""
            snomed_code = fallback_code
            if cui and not snomed_code:
                snomed_code = self._get_snomed_code_for_cui(cui)
            candidates.append(
                SnomedCandidate(
                    cui=cui,
                    code=snomed_code,
                    display=str(name) if isinstance(name, str) else "",
                    ontology=str(root) if isinstance(root, str) else "SNOMEDCT_US",
                    confidence=0.9,
                )
            )
        return candidates

    def _get_snomed_code_for_cui(self, cui: str) -> str:
        """Fetch the SNOMED code associated with a UMLS CUI."""
        cache_key = f"snomed_code:{cui}"
        cached = cast(str | None, self._cache.get(cache_key))
        if cached is not None:
            return cached

        url = f"{self.base_url.rstrip('/')}/content/current/CUI/{cui}/atoms"
        params: dict[str, str | int] = {
            "sabs": "SNOMEDCT_US",
            "pageSize": 1,
            "apiKey": self.api_key or "",
        }
        try:
            data = self._request_with_retry(url, params)
            snomed_code = self._extract_snomed_code_from_atoms(data)
            if self._cache_ttl:
                self._cache.set(cache_key, snomed_code, expire=self._cache_ttl)
            return snomed_code
        except (UmlsApiError, httpx.RequestError) as exc:
            logger.warning("UMLS API error for CUI atoms %s: %s", cui, exc)
            return ""

    @staticmethod
    def _extract_snomed_code_from_atoms(data: dict[str, object]) -> str:
        result = data.get("result", {})
        if not isinstance(result, dict):
            return ""
        results = result.get("results", [])
        if not isinstance(results, Sequence) or not results:
            return ""
        first = results[0]
        if not isinstance(first, dict):
            return ""
        for key in ("code", "sourceConcept", "sourceConceptId", "sourceUi"):
            value = first.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        self._http.close()
        try:
            self._cache.close()
        except (OSError, AttributeError):
            # Expected cleanup errors: cache may already be closed or file system errors
            pass

    def __del__(self) -> None:  # pragma: no cover
        """Fallback cleanup if not used as context manager."""
        try:
            self._http.close()
        except Exception:
            # Destructors should be defensive and catch all exceptions
            # to prevent errors during garbage collection
            pass

    def get_concept_details(self, cui: str) -> dict[str, object]:
        """Get detailed information about a UMLS concept including semantic types.

        Args:
            cui: UMLS Concept Unique Identifier.

        Returns:
            Dictionary with concept details including semantic types.

        Raises:
            ValueError: If CUI is empty.
        """
        if not cui.strip():
            raise ValueError("cui is required")

        cache_key = f"concept:{cui}"
        cached = cast(dict[str, object] | None, self._cache.get(cache_key))
        if cached is not None:
            return cached

        url = f"{self.base_url.rstrip('/')}/content/current/CUI/{cui}"
        params: dict[str, str | int] = {
            "apiKey": self.api_key or "",
        }

        try:
            data = self._request_with_retry(url, params)
            if self._cache_ttl:
                self._cache.set(cache_key, data, expire=self._cache_ttl)
            return data
        except (UmlsApiError, httpx.RequestError) as exc:
            logger.warning("UMLS API error for CUI %s: %s", cui, exc)
            return {}

    def get_snomed_details(self, snomed_code: str) -> dict[str, object]:
        """Get UMLS details for a SNOMED CT source-asserted identifier.

        Args:
            snomed_code: SNOMED CT code (source identifier).

        Returns:
            Dictionary with source-asserted details from UMLS.

        Raises:
            ValueError: If SNOMED code is empty.
        """
        if not snomed_code.strip():
            raise ValueError("snomed_code is required")

        cache_key = f"snomed_details:{snomed_code}"
        cached = cast(dict[str, object] | None, self._cache.get(cache_key))
        if cached is not None:
            return cached

        url = (
            f"{self.base_url.rstrip('/')}/content/current/source/SNOMEDCT_US/"
            f"{snomed_code}"
        )
        params: dict[str, str | int] = {
            "apiKey": self.api_key or "",
        }
        try:
            data = self._request_with_retry(url, params)
            if self._cache_ttl:
                self._cache.set(cache_key, data, expire=self._cache_ttl)
            return data
        except (UmlsApiError, httpx.RequestError) as exc:
            logger.warning(
                "UMLS API error for SNOMED code %s: %s", snomed_code, exc
            )
            return {}

    def get_semantic_types(self, cui: str) -> list[str]:
        """Get semantic types (TUIs) for a UMLS concept.

        Args:
            cui: UMLS Concept Unique Identifier.

        Returns:
            List of semantic type identifiers (TUIs).
        """
        details = self.get_concept_details(cui)
        result = details.get("result", {})
        if not isinstance(result, dict):
            return []

        semantic_types = result.get("semanticTypes", [])
        if not isinstance(semantic_types, Sequence):
            return []

        tuis: list[str] = []
        for st in semantic_types:
            if isinstance(st, dict):
                name = st.get("name")
                if isinstance(name, str) and name.startswith("T"):
                    tuis.append(name)
        return tuis

    def clear_cache(self) -> None:
        """Clear the search cache."""
        self._cache.clear()

    @staticmethod
    def _parse_cache_ttl(value: str | None) -> int:
        if not value:
            return 7 * 24 * 60 * 60
        try:
            ttl = int(value)
        except ValueError:
            return 7 * 24 * 60 * 60
        return ttl if ttl > 0 else 7 * 24 * 60 * 60

    def check_health(self) -> dict[str, Any]:
        """Check UMLS API health with a lightweight query.

        Returns:
            Dictionary with health status information.
        """
        import time

        try:
            start = time.time()
            # Use a simple, cached query for health check
            self.search_snomed("diabetes", limit=1)
            elapsed_ms = (time.time() - start) * 1000

            return {
                "status": "healthy",
                "api_available": True,
                "response_time_ms": elapsed_ms,
                "cache_status": "operational",
            }
        except UmlsApiServerError as e:
            return {
                "status": "degraded",
                "api_available": False,
                "last_error": f"Server error: {e.message}",
                "cache_status": "operational",
            }
        except UmlsApiClientError as e:
            return {
                "status": "unhealthy",
                "api_available": False,
                "last_error": f"Client error: {e.message}",
                "cache_status": "operational",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "api_available": False,
                "last_error": f"Unexpected error: {str(e)}",
                "cache_status": "unknown",
            }


@contextmanager
def umls_client_context(
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
) -> Iterator["UmlsClient"]:
    """Provide a managed UmlsClient for safe usage elsewhere."""
    client = UmlsClient(base_url=base_url, api_key=api_key, timeout=timeout)
    try:
        yield client
    finally:
        client.close()


FIELD_PATTERNS: list[tuple[re.Pattern[str], str, tuple[int, ...]]] = [
    (re.compile(r"age\s*(>=|<=|>|<|=)\s*(\d+)", re.I), "demographics.age", (1, 2)),
    (re.compile(r"age\s*(\d+)\s*-\s*(\d+)", re.I), "demographics.age", (1, 2)),
    (
        re.compile(r"(\d+)\s*-\s*(\d+)\s*years?\s*(?:of\s*age|old)?", re.I),
        "demographics.age",
        (1, 2),
    ),
    (
        re.compile(r"bmi\s*(>=|<=|>|<|=)\s*(\d+(?:\.\d+)?)", re.I),
        "vitals.bmi",
        (1, 2),
    ),
    (
        re.compile(
            r"ecog\s*(?:ps|performance\s*status)?\s*(>=|<=|>|<|=)?\s*(\d)",
            re.I,
        ),
        "performance.ecog",
        (1, 2),
    ),
    (
        re.compile(r"ecog\s*(?:ps|performance\s*status)?\s*(\d)\s*-\s*(\d)", re.I),
        "performance.ecog",
        (1, 2),
    ),
    (re.compile(r"\b(male|female)\b", re.I), "demographics.sex", (1,)),
    (
        re.compile(r"\b(pregnant|pregnancy|breastfeeding)\b", re.I),
        "conditions.pregnancy",
        (1,),
    ),
]


def propose_field_mapping(criterion_text: str) -> list[FieldMappingSuggestion]:
    """Propose field/relation/value mappings for a criterion.

    Args:
        criterion_text: Criterion text span to map.

    Returns:
        A list of field mapping suggestions.

    Raises:
        ValueError: If the criterion text is empty.
    """
    if not criterion_text.strip():
        raise ValueError("criterion_text is required")

    suggestions: list[FieldMappingSuggestion] = []
    range_fields_added: set[str] = set()

    for pattern, field, groups in FIELD_PATTERNS:
        match = pattern.search(criterion_text)
        if not match:
            continue

        if field in {"demographics.age", "performance.ecog"} and len(groups) == 2:
            if "-" in match.group(0):
                if field in range_fields_added:
                    continue
                low, high = match.group(groups[0]), match.group(groups[1])
                suggestions.append(FieldMappingSuggestion(field, ">=", low, 0.85))
                suggestions.append(FieldMappingSuggestion(field, "<=", high, 0.85))
                range_fields_added.add(field)
                continue

        if field == "demographics.sex":
            value = match.group(groups[0]).lower()
            suggestions.append(FieldMappingSuggestion(field, "=", value, 0.9))
            continue

        if field == "conditions.pregnancy":
            suggestions.append(FieldMappingSuggestion(field, "=", "true", 0.85))
            continue

        if len(groups) == 2:
            relation = match.group(groups[0]) or "="
            value = match.group(groups[1])
            suggestions.append(FieldMappingSuggestion(field, relation, value, 0.87))

    return suggestions
