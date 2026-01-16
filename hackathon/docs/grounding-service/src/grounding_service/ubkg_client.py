"""UBKG REST client stub."""

import re
from dataclasses import dataclass
from typing import List


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
    """Client for UBKG REST search endpoints.

    Args:
        base_url: Base URL for the UBKG REST API.

    Examples:
        >>> UbkgClient().base_url
        'https://ubkg-api.xconsortia.org'

    Notes:
        This is a wireframe stub; HTTP calls and caching are not implemented.
        Field mapping suggestions are handled alongside grounding in the
        production service.
    """

    def __init__(self, base_url: str = "https://ubkg-api.xconsortia.org") -> None:
        """Initialize the client with a base URL."""
        self.base_url = base_url

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

        Notes:
            The production version will call the UBKG search endpoint and map
            results into ``UbkgCandidate`` instances.
        """
        if not query.strip():
            raise ValueError("query is required")

        lowered = query.lower()
        candidates: List[UbkgCandidate] = []
        if "melanoma" in lowered:
            candidates.append(
                UbkgCandidate(
                    code="372244006",
                    display="Malignant melanoma, stage III",
                    ontology="SNOMED CT",
                    confidence=0.92,
                )
            )
        elif "age" in lowered:
            candidates.append(
                UbkgCandidate(
                    code="371273006",
                    display="Age",
                    ontology="SNOMED CT",
                    confidence=0.85,
                )
            )
        elif "pregnant" in lowered:
            candidates.append(
                UbkgCandidate(
                    code="77386006",
                    display="Pregnant",
                    ontology="SNOMED CT",
                    confidence=0.88,
                )
            )
        return candidates[:limit]


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
        This is a wireframe stub. The production implementation will use
        a MedGemma adapter or rule-based parser for field mapping.
    """
    if not criterion_text.strip():
        raise ValueError("criterion_text is required")

    match = re.search(r"age\s*(>=|<=|=|>|<)\s*(\d+)", criterion_text, re.IGNORECASE)
    if not match:
        return []

    relation, value = match.group(1), match.group(2)
    return [
        FieldMappingSuggestion(
            field="demographics.age",
            relation=relation,
            value=value,
            confidence=0.87,
        )
    ]
