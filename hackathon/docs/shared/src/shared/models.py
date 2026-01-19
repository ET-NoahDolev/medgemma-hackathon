"""Shared data models for API and UI."""

from dataclasses import dataclass, field
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
    evidence_spans: List["EvidenceSpan"] = field(default_factory=list)


@dataclass
class EvidenceSpan:
    """Evidence span linking criterion to source document.

    Args:
        start_char: Starting character offset in source.
        end_char: Ending character offset in source.
        source_doc_id: Document identifier for provenance.
    """

    start_char: int
    end_char: int
    source_doc_id: str


@dataclass
class FieldMapping:
    """Field/relation/value mapping attached to a criterion.

    Args:
        field: Target field path (e.g., demographics.age).
        relation: Comparison operator (e.g., >, >=, =).
        value: Normalized value string (e.g., 75).
        confidence: Optional confidence score.

    Examples:
        >>> FieldMapping(
        ...     field="demographics.age",
        ...     relation=">",
        ...     value="75",
        ...     confidence=0.87,
        ... )
        FieldMapping(
        ...     field='demographics.age',
        ...     relation='>',
        ...     value='75',
        ...     confidence=0.87,
        ... )
    """

    field: str
    relation: str
    value: str
    confidence: Optional[float] = None

    def to_string(self) -> str:
        """Serialize to pipe-delimited string."""
        return f"{self.field}|{self.relation}|{self.value}"

    @classmethod
    def from_string(cls, value: str) -> "FieldMapping":
        """Deserialize from pipe-delimited string."""
        parts = value.split("|")
        if len(parts) != 3:
            raise ValueError(
                "Invalid field mapping string: "
                f"'{value}'. Expected format 'field|relation|value' "
                "(e.g., 'demographics.age|>=|18')."
            )
        return cls(field=parts[0], relation=parts[1], value=parts[2])


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
    snomed_code_added: Optional[str] = None
    snomed_code_removed: Optional[str] = None
    field_mapping_added: Optional[str] = None
    field_mapping_removed: Optional[str] = None


def build_criterion(
    *,
    id: str = "crit-1",
    text: str = "Age >= 18 years",
    criterion_type: str = "inclusion",
    confidence: float = 0.92,
    snomed_codes: Optional[List[str]] = None,
    evidence_spans: Optional[List[EvidenceSpan]] = None,
) -> Criterion:
    """Create a Criterion instance with defaults for tests and examples."""
    return Criterion(
        id=id,
        text=text,
        criterion_type=criterion_type,
        confidence=confidence,
        snomed_codes=snomed_codes or ["371273006"],
        evidence_spans=evidence_spans or [],
    )


def build_field_mapping(
    *,
    field: str = "demographics.age",
    relation: str = ">=",
    value: str = "18",
    confidence: Optional[float] = 0.87,
) -> FieldMapping:
    """Create a FieldMapping instance with defaults for tests and examples."""
    return FieldMapping(
        field=field,
        relation=relation,
        value=value,
        confidence=confidence,
    )


def build_protocol(
    *,
    id: str = "proto-1",
    title: str = "Example Trial",
    nct_id: str = "NCT00000000",
    condition: str = "Melanoma",
    phase: str = "Phase 2",
) -> Protocol:
    """Create a Protocol instance with defaults for tests and examples."""
    return Protocol(
        id=id,
        title=title,
        nct_id=nct_id,
        condition=condition,
        phase=phase,
    )


def build_document(
    *,
    id: str = "doc-1",
    protocol_id: str = "proto-1",
    text: str = "Inclusion: Age >= 18.",
    source_url: Optional[str] = None,
) -> Document:
    """Create a Document instance with defaults for tests and examples."""
    return Document(
        id=id,
        protocol_id=protocol_id,
        text=text,
        source_url=source_url,
    )


def build_grounding_candidate(
    *,
    code: str = "372244006",
    display: str = "Malignant melanoma, stage III",
    confidence: float = 0.92,
) -> GroundingCandidate:
    """Create a GroundingCandidate instance with defaults for tests and examples."""
    return GroundingCandidate(
        code=code,
        display=display,
        confidence=confidence,
    )


def build_hitl_edit(
    *,
    id: str = "edit-1",
    criterion_id: str = "crit-1",
    action: str = "accept",
    note: Optional[str] = "Matches protocol text",
    snomed_code_added: Optional[str] = None,
    snomed_code_removed: Optional[str] = None,
    field_mapping_added: Optional[str] = None,
    field_mapping_removed: Optional[str] = None,
) -> HitlEdit:
    """Create a HitlEdit instance with defaults for tests and examples."""
    return HitlEdit(
        id=id,
        criterion_id=criterion_id,
        action=action,
        note=note,
        snomed_code_added=snomed_code_added,
        snomed_code_removed=snomed_code_removed,
        field_mapping_added=field_mapping_added,
        field_mapping_removed=field_mapping_removed,
    )
