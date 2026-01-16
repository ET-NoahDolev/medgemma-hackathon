"""Extraction pipeline stubs for MedGemma Task A."""

from dataclasses import dataclass
from typing import List


@dataclass
class Criterion:
    """Atomic inclusion/exclusion criterion extracted from a protocol.

    Args:
        text: The criterion text span.
        criterion_type: Inclusion or exclusion label.
        confidence: Model confidence score from 0.0 to 1.0.

    Examples:
        >>> Criterion(
        ...     text="Age >= 18 years",
        ...     criterion_type="inclusion",
        ...     confidence=0.92,
        ... )
        Criterion(text='Age >= 18 years', criterion_type='inclusion', confidence=0.92)

    Notes:
        Evidence spans, grounding candidates, and field mappings are stored
        downstream by the API.
    """

    text: str
    criterion_type: str
    confidence: float


def extract_criteria(document_text: str) -> List[Criterion]:
    """Extract atomic inclusion/exclusion criteria from protocol text.

    Args:
        document_text: Raw protocol text or extracted PDF text.

    Returns:
        A list of extracted criteria with type and confidence scores.

    Raises:
        ValueError: If the document text is empty or not parseable.

    Examples:
        >>> extract_criteria("Inclusion: Age >= 18 years.")
        []

    Notes:
        This is a wireframe stub. The production pipeline will use MedGemma
        for extraction and classification, with evidence spans attached.
    """
    if not document_text.strip():
        raise ValueError("document_text is required")

    criteria: List[Criterion] = []
    for sentence in split_into_candidate_sentences(document_text):
        criteria.append(
            Criterion(
                text=sentence,
                criterion_type=classify_criterion_type(sentence),
                confidence=0.9,
            )
        )
    return criteria


def split_into_candidate_sentences(document_text: str) -> List[str]:
    """Split protocol text into candidate sentences for extraction.

    Args:
        document_text: Raw protocol text or extracted PDF text.

    Returns:
        Sentence-level candidates for criteria extraction.

    Raises:
        ValueError: If the input text is empty.

    Examples:
        >>> split_into_candidate_sentences("Inclusion: Age >= 18. Exclusion: Pregnant.")
        []

    Notes:
        Intended to be replaced by a robust section parser and sentence
        splitter tuned for clinical trial formatting.
    """
    if not document_text.strip():
        raise ValueError("document_text is required")

    normalized = document_text.replace("\n", " ").strip()
    raw_sentences = [segment.strip() for segment in normalized.split(".")]
    candidates: List[str] = []
    for sentence in raw_sentences:
        if not sentence:
            continue
        lowered = sentence.lower()
        if lowered.startswith("inclusion:"):
            sentence = sentence[len("inclusion:") :].strip()
        elif lowered.startswith("exclusion:"):
            sentence = sentence[len("exclusion:") :].strip()
        if sentence:
            candidates.append(sentence)
    return candidates


def classify_criterion_type(candidate_text: str) -> str:
    """Classify a criterion candidate as inclusion or exclusion.

    Args:
        candidate_text: Candidate sentence or span to classify.

    Returns:
        Either ``"inclusion"`` or ``"exclusion"``.

    Raises:
        ValueError: If the candidate text is empty.

    Examples:
        >>> classify_criterion_type("Age >= 18 years")
        'inclusion'

    Notes:
        This stub is a placeholder for MedGemma classification.
    """
    if not candidate_text.strip():
        raise ValueError("candidate_text is required")

    lowered = candidate_text.lower()
    if "exclusion" in lowered or "exclude" in lowered or "pregnant" in lowered:
        return "exclusion"
    return "inclusion"
