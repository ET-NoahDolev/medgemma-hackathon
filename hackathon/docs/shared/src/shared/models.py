"""Shared data models for API and UI."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Criterion:
    """Atomic criterion extracted from a protocol.

    Args:
        id: Stable identifier for the criterion.
        text: Criterion text.
        criterion_type: Inclusion or exclusion label.
        confidence: Model confidence score.
        snomed_codes: SNOMED codes attached to the criterion.

    Examples:
        >>> Criterion(
        ...     id="crit-1",
        ...     text="Age >= 18 years",
        ...     criterion_type="inclusion",
        ...     confidence=0.92,
        ...     snomed_codes=["371273006"],
        ... )
        Criterion(
        ...     id='crit-1',
        ...     text='Age >= 18 years',
        ...     criterion_type='inclusion',
        ...     confidence=0.92,
        ...     snomed_codes=['371273006'],
        ... )

    Notes:
        Evidence spans and grounding candidates are stored separately.
    """

    id: str
    text: str
    criterion_type: str
    confidence: float
    snomed_codes: List[str]


@dataclass
class Protocol:
    """Protocol metadata tracked by the API.

    Args:
        id: Stable protocol identifier.
        title: Human-readable trial title.
        nct_id: ClinicalTrials.gov identifier.
        condition: Primary disease/condition.
        phase: Trial phase label.

    Examples:
        >>> Protocol(
        ...     id="proto-1",
        ...     title="Example Trial",
        ...     nct_id="NCT00000000",
        ...     condition="Melanoma",
        ...     phase="Phase 2",
        ... )
        Protocol(
        ...     id='proto-1',
        ...     title='Example Trial',
        ...     nct_id='NCT00000000',
        ...     condition='Melanoma',
        ...     phase='Phase 2',
        ... )
    """

    id: str
    title: str
    nct_id: str
    condition: str
    phase: str


@dataclass
class Document:
    """Protocol document content and provenance.

    Args:
        id: Document identifier.
        protocol_id: Associated protocol identifier.
        text: Extracted protocol text.
        source_url: Optional source URL for provenance.

    Examples:
        >>> Document(
        ...     id="doc-1",
        ...     protocol_id="proto-1",
        ...     text="Inclusion: ...",
        ...     source_url=None,
        ... )
        Document(
        ...     id='doc-1',
        ...     protocol_id='proto-1',
        ...     text='Inclusion: ...',
        ...     source_url=None,
        ... )
    """

    id: str
    protocol_id: str
    text: str
    source_url: Optional[str]


@dataclass
class GroundingCandidate:
    """SNOMED candidate for a criterion grounding decision.

    Args:
        code: SNOMED concept code.
        display: Human-readable concept description.
        confidence: Model or retrieval confidence score.

    Examples:
        >>> GroundingCandidate(
        ...     code="372244006",
        ...     display="Malignant melanoma, stage III",
        ...     confidence=0.92,
        ... )
        GroundingCandidate(
        ...     code='372244006',
        ...     display='Malignant melanoma, stage III',
        ...     confidence=0.92,
        ... )
    """

    code: str
    display: str
    confidence: float


@dataclass
class HitlEdit:
    """Human-in-the-loop edit captured from a nurse reviewer.

    Args:
        id: Edit identifier.
        criterion_id: Criterion updated by the reviewer.
        action: Action label (accept, reject, add, edit).
        note: Optional rationale or comment.

    Examples:
        >>> HitlEdit(
        ...     id="edit-1",
        ...     criterion_id="crit-1",
        ...     action="accept",
        ...     note="Matches protocol text",
        ... )
        HitlEdit(
        ...     id='edit-1',
        ...     criterion_id='crit-1',
        ...     action='accept',
        ...     note='Matches protocol text',
        ... )
    """

    id: str
    criterion_id: str
    action: str
    note: Optional[str]
