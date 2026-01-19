"""Extraction pipeline for MedGemma Task A."""

import re
from dataclasses import dataclass
from typing import Dict


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


def extract_criteria(document_text: str) -> list[Criterion]:
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
        This baseline implementation uses section detection and rule-based
        classification for prototyping.
    """
    if not document_text.strip():
        raise ValueError("document_text is required")

    sections = detect_sections(document_text)
    criteria: list[Criterion] = []

    for section_type, section_text in sections.items():
        sentences = split_into_candidate_sentences(section_text)
        for sentence in sentences:
            criterion_type = classify_criterion_type(sentence, section=section_type)
            confidence = 0.9 if section_type != "unknown" else 0.7
            criteria.append(
                Criterion(
                    text=sentence,
                    criterion_type=criterion_type,
                    confidence=confidence,
                )
            )

    return criteria


def split_into_candidate_sentences(text: str) -> list[str]:
    """Split text into candidate criterion sentences.

    Args:
        text: Section text to split.

    Returns:
        List of candidate sentences.
    """
    if not text.strip():
        return []

    if "\n" not in text and (
        INLINE_INCLUSION.search(text) or INLINE_EXCLUSION.search(text)
    ):
        return _split_inline_criteria(text)

    lines = text.split("\n")
    candidates: list[str] = []
    for line in lines:
        cleaned = _normalize_candidate(BULLET_PATTERN.sub("", line))
        if not cleaned:
            continue
        if INCLUSION_HEADER.match(cleaned) or EXCLUSION_HEADER.match(cleaned):
            continue
        candidates.append(cleaned)
    return candidates


def _split_inline_criteria(text: str) -> list[str]:
    """Split inline Inclusion/Exclusion sentences into criteria."""
    normalized = text.replace("\n", " ").strip()
    raw_sentences = [segment.strip() for segment in normalized.split(".")]
    candidates: list[str] = []
    for sentence in raw_sentences:
        if not sentence:
            continue
        lowered = sentence.lower()
        if lowered.startswith("inclusion:"):
            sentence = sentence[len("inclusion:") :].strip()
        elif lowered.startswith("exclusion:"):
            sentence = sentence[len("exclusion:") :].strip()
        sentence = _normalize_candidate(sentence)
        if sentence:
            candidates.append(sentence)
    return candidates


def _normalize_candidate(text: str) -> str:
    """Normalize candidate criteria text."""
    return text.strip().rstrip(".")


def classify_criterion_type(candidate_text: str, section: str = "unknown") -> str:
    """Classify criterion as inclusion or exclusion.

    Args:
        candidate_text: Criterion text.
        section: Section context ("inclusion", "exclusion", or "unknown").

    Returns:
        Either "inclusion" or "exclusion".
    """
    if not candidate_text.strip():
        raise ValueError("candidate_text is required")

    lowered = candidate_text.lower()
    for keyword in EXCLUSION_KEYWORDS:
        if keyword in lowered:
            return "exclusion"

    if section == "exclusion":
        return "exclusion"

    return "inclusion"


INCLUSION_HEADER = re.compile(
    r"(?:^|\n)\s*(?:inclusion\s*criteria|eligibility\s*criteria|include)\s*:?\s*(?:\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
EXCLUSION_HEADER = re.compile(
    r"(?:^|\n)\s*(?:exclusion\s*criteria|ineligibility\s*criteria|exclude)\s*:?\s*(?:\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
BULLET_PATTERN = re.compile(r"^\s*(?:[-•*]|\d+[.)\]]|\([a-z]\))\s*", re.MULTILINE)
INLINE_INCLUSION = re.compile(r"\binclusion\b\s*:", re.IGNORECASE)
INLINE_EXCLUSION = re.compile(r"\bexclusion\b\s*:", re.IGNORECASE)

EXCLUSION_KEYWORDS = [
    "pregnant",
    "pregnancy",
    "breastfeeding",
    "lactating",
    "exclude",
    "excluded",
    "not eligible",
    "ineligible",
    "contraindicated",
    "cannot",
    "no prior",
    "none of",
    "history of",
    "active disease",
    "known allergy",
]


def detect_sections(document_text: str) -> Dict[str, str]:
    """Detect inclusion/exclusion sections in protocol text.

    Args:
        document_text: Raw protocol text.

    Returns:
        Dict mapping section type to section content.
    """
    sections: Dict[str, str] = {}

    inc_match = INCLUSION_HEADER.search(document_text)
    exc_match = EXCLUSION_HEADER.search(document_text)

    if not inc_match and not exc_match:
        inc_match = INLINE_INCLUSION.search(document_text)
        exc_match = INLINE_EXCLUSION.search(document_text)

    if inc_match and exc_match:
        if inc_match.start() < exc_match.start():
            sections["inclusion"] = document_text[inc_match.end() : exc_match.start()]
            sections["exclusion"] = document_text[exc_match.end() :]
        else:
            sections["exclusion"] = document_text[exc_match.end() : inc_match.start()]
            sections["inclusion"] = document_text[inc_match.end() :]
    elif inc_match:
        sections["inclusion"] = document_text[inc_match.end() :]
    elif exc_match:
        sections["exclusion"] = document_text[exc_match.end() :]

    return sections
