"""UMLS SNOMED client with disk cache and retry.

Environment variables:
- UMLS_API_KEY: API key for UMLS (required).
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
from typing import Sequence, cast

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
        code: SNOMED concept code.
        display: Human-readable concept name.
        ontology: Ontology label (e.g., SNOMEDCT_US).
        confidence: Confidence or relevance score.
    """

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
        self.api_key = api_key or os.getenv("UMLS_API_KEY")
        env_timeout = os.getenv("UMLS_TIMEOUT_SECONDS")
        self.timeout = (
            float(env_timeout)
            if env_timeout
            else (timeout if timeout is not None else 10.0)
        )
        if not self.api_key:
            raise ValueError("UMLS_API_KEY is required")
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
        """
        if not query.strip():
            raise ValueError("query is required")

        cache_key = f"snomed:{query.lower()}:{limit}"
        cached = cast(list[SnomedCandidate] | None, self._cache.get(cache_key))
        if cached is not None:
            return cached

        candidates = self._fetch_from_api(query, limit)
        if self._cache_ttl:
            self._cache.set(cache_key, candidates, expire=self._cache_ttl)
        return candidates

    def _fetch_from_api(self, query: str, limit: int) -> list[SnomedCandidate]:
        """Execute HTTP request to UMLS API with retry on transient errors."""
        url = f"{self.base_url.rstrip('/')}/search/current"
        params: dict[str, str | int] = {
            "string": query,
            "sabs": "SNOMEDCT_US",
            "returnIdType": "code",
            "pageSize": limit,
            "apiKey": self.api_key or "",
        }

        try:
            data = self._request_with_retry(url, params)
            return self._parse_response(data, limit)
        except httpx.HTTPStatusError as exc:
            logger.warning("UMLS API HTTP error: %s", exc)
            return []
        except httpx.RequestError as exc:
            logger.warning("UMLS API request error: %s", exc)
            return []

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, _ServerError)),
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
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def _parse_response(
        self,
        data: dict[str, object],
        limit: int,
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
            candidates.append(
                SnomedCandidate(
                    code=str(ui) if isinstance(ui, (str, int)) else "",
                    display=str(name) if isinstance(name, str) else "",
                    ontology=str(root) if isinstance(root, str) else "SNOMEDCT_US",
                    confidence=0.9,
                )
            )
        return candidates

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        self._http.close()
        try:
            self._cache.close()
        except Exception:
            pass

    def __del__(self) -> None:  # pragma: no cover
        """Fallback cleanup if not used as context manager."""
        try:
            self._http.close()
        except Exception:
            pass

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
