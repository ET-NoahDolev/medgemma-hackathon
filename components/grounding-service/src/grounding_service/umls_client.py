"""UMLS REST client."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import List, Sequence

import httpx

logger = logging.getLogger(__name__)

UMLS_DEFAULT_URL = "https://uts-ws.nlm.nih.gov/rest"


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
        self._cache: dict[str, list[SnomedCandidate]] = {}

    def search_snomed(self, query: str, limit: int = 5) -> List[SnomedCandidate]:
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
        if not self.api_key:
            raise ValueError("UMLS_API_KEY is required")

        cache_key = f"{query.lower()}:{limit}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        candidates = self._fetch_from_api(query, limit)
        self._cache[cache_key] = candidates
        return candidates

    def _fetch_from_api(self, query: str, limit: int) -> List[SnomedCandidate]:
        """Execute HTTP request to UMLS API."""
        try:
            response = httpx.get(
                f"{self.base_url.rstrip('/')}/search/current",
                params={
                    "string": query,
                    "sabs": "SNOMEDCT_US",
                    "returnIdType": "code",
                    "pageSize": limit,
                    "apiKey": self.api_key,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return self._parse_response(response.json(), limit)
        except Exception as exc:
            logger.warning("UMLS API error: %s", exc)
            return []

    def _parse_response(
        self,
        data: dict[str, object],
        limit: int,
    ) -> List[SnomedCandidate]:
        """Parse UMLS API response into candidates."""
        result = data.get("result", {})
        if not isinstance(result, dict):
            return []
        results = result.get("results", [])
        if not isinstance(results, Sequence):
            return []

        candidates: List[SnomedCandidate] = []
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

    def clear_cache(self) -> None:
        """Clear the search cache."""
        self._cache.clear()


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


def propose_field_mapping(criterion_text: str) -> List[FieldMappingSuggestion]:
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

    suggestions: List[FieldMappingSuggestion] = []
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
