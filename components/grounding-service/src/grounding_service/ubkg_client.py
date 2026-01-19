"""UBKG REST client."""

import logging
import re
from dataclasses import dataclass
from typing import List, Sequence

import httpx

logger = logging.getLogger(__name__)

UBKG_DEFAULT_URL = "https://ubkg-api.xconsortia.org"


@dataclass
class UbkgCandidate:
    """SNOMED candidate returned from UBKG.

    Args:
        code: SNOMED concept code.
        display: Human-readable concept name.
        ontology: Ontology label (e.g., SNOMED CT).
        confidence: Confidence or relevance score.

    Examples:
        >>> UbkgCandidate(
        ...     code="372244006",
        ...     display="Malignant melanoma, stage III",
        ...     ontology="SNOMED CT",
        ...     confidence=0.92,
        ... )
        UbkgCandidate(
        ...     code='372244006',
        ...     display='Malignant melanoma, stage III',
        ...     ontology='SNOMED CT',
        ...     confidence=0.92,
        ... )

    Notes:
        UBKG returns richer fields; this wireframe focuses on what the HITL UI needs.
    """

    code: str
    display: str
    ontology: str
    confidence: float


@dataclass
class FieldMappingSuggestion:
    """Field/relation/value mapping suggestion for a criterion.

    Args:
        field: Target field path (e.g., demographics.age).
        relation: Comparison operator (e.g., >, >=, =).
        value: Normalized value string (e.g., 75).
        confidence: Confidence or relevance score.

    Examples:
        >>> FieldMappingSuggestion(
        ...     field="demographics.age",
        ...     relation=">",
        ...     value="75",
        ...     confidence=0.87,
        ... )
        FieldMappingSuggestion(
        ...     field='demographics.age',
        ...     relation='>',
        ...     value='75',
        ...     confidence=0.87,
        ... )

    Notes:
        This is a wireframe stub; production mapping will come from a model.
    """

    field: str
    relation: str
    value: str
    confidence: float


class UbkgClient:
    """Client for UBKG REST search endpoints with caching.

    Args:
        base_url: Base URL for the UBKG REST API.

    Examples:
        >>> UbkgClient().base_url
        'https://ubkg-api.xconsortia.org'

    Notes:
        Results are cached in-memory by query/limit for faster repeated calls.
    """

    def __init__(self, base_url: str = UBKG_DEFAULT_URL, timeout: float = 10.0) -> None:
        """Initialize the client with a base URL."""
        self.base_url = base_url
        self.timeout = timeout
        self._cache: dict[str, list[UbkgCandidate]] = {}

    def search_snomed(self, query: str, limit: int = 5) -> List[UbkgCandidate]:
        """Search SNOMED concepts via UBKG.

        Args:
            query: Free-text clinical concept to search.
            limit: Maximum number of candidates to return.

        Returns:
            A list of candidate SNOMED concepts.

        Raises:
            ValueError: If the query is empty.

        Examples:
            >>> UbkgClient().search_snomed("stage III melanoma")
            []

        """
        if not query.strip():
            raise ValueError("query is required")

        cache_key = f"{query.lower()}:{limit}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        candidates = self._fetch_from_api(query, limit)
        self._cache[cache_key] = candidates
        return candidates

    def _fetch_from_api(self, query: str, limit: int) -> List[UbkgCandidate]:
        """Execute HTTP request to UBKG API."""
        try:
            response = httpx.get(
                f"{self.base_url}/concepts/search",
                params={"query": query, "sab": "SNOMEDCT_US", "limit": limit},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return self._parse_response(response.json(), limit)
        except Exception as exc:
            logger.warning("UBKG API error: %s, falling back to local search", exc)
            return self._fallback_search(query, limit)

    def _parse_response(
        self,
        data: Sequence[dict[str, object]],
        limit: int,
    ) -> List[UbkgCandidate]:
        """Parse UBKG API response into candidates."""
        candidates: List[UbkgCandidate] = []
        for item in data[:limit]:
            candidates.append(
                UbkgCandidate(
                    code=str(item.get("ui", "")),
                    display=str(item.get("name", "")),
                    ontology="SNOMED CT",
                    confidence=0.9,
                )
            )
        return candidates

    def _fallback_search(self, query: str, limit: int) -> List[UbkgCandidate]:
        """Fallback to local SNOMED subset when API unavailable."""
        lowered = query.lower()
        candidates: List[UbkgCandidate] = []
        if "melanoma" in lowered:
            candidates.append(
                UbkgCandidate(
                    code="372244006",
                    display="Malignant melanoma, stage III",
                    ontology="SNOMED CT",
                    confidence=0.7,
                )
            )
        if "age" in lowered:
            candidates.append(
                UbkgCandidate(
                    code="371273006",
                    display="Age",
                    ontology="SNOMED CT",
                    confidence=0.6,
                )
            )
        if "pregnant" in lowered:
            candidates.append(
                UbkgCandidate(
                    code="77386006",
                    display="Pregnant",
                    ontology="SNOMED CT",
                    confidence=0.6,
                )
            )
        return candidates[:limit]

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

    Examples:
        >>> propose_field_mapping("Age >= 75 years")
        []

    Notes:
        This rule-based mapper targets common screening patterns.
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
