"""Pydantic schemas for structured agent output."""

from typing import Literal

from pydantic import BaseModel, Field


class GroundedTerm(BaseModel):
    """Single grounded term from a criterion."""

    snippet: str = Field(description="Text span being grounded")
    raw_criterion_text: str = Field(description="Full criterion sentence")
    criterion_type: Literal["inclusion", "exclusion"] = Field(
        description="Criterion type label"
    )
    umls_concept: str | None = Field(
        default=None, description="UMLS concept preferred name"
    )
    umls_id: str | None = Field(
        default=None, description="UMLS CUI (e.g., C0011860)"
    )
    snomed_code: str | None = Field(default=None, description="SNOMED CT code")
    relation: str | None = Field(
        default=None, description="Comparison: =, >, >=, <, <=, within"
    )
    value: str | None = Field(default=None, description="Extracted value")
    unit: str | None = Field(default=None, description="Unit of measurement")
    computed_as: str | None = Field(
        default=None, description="Expression if computed, e.g. 'today() - birthDate'"
    )
    relation_confidence: float = Field(
        0.0, ge=0, le=1, description="Relation extraction confidence"
    )
    value_confidence: float = Field(
        0.0, ge=0, le=1, description="Value extraction confidence"
    )
    umls_confidence: float = Field(
        0.0, ge=0, le=1, description="UMLS match confidence"
    )
    confidence: float = Field(ge=0, le=1, description="Confidence score")


class GroundingResult(BaseModel):
    """Complete grounding result from agent."""

    terms: list[GroundedTerm] = Field(description="List of grounded terms")
    logical_operator: str | None = Field(
        default=None, description="AND/OR between terms"
    )
    reasoning: str = Field(description="Agent reasoning trace")


class GroundingBatchItem(BaseModel):
    """Grounding result for a single criterion in a batch."""

    index: int = Field(description="Index of the criterion in the batch")
    criterion_text: str = Field(description="Original criterion text")
    criterion_type: Literal["inclusion", "exclusion"] = Field(
        description="Criterion type label"
    )
    terms: list[GroundedTerm] = Field(description="List of grounded terms")
    logical_operator: str | None = Field(
        default=None, description="AND/OR between terms"
    )
    reasoning: str = Field(description="Agent reasoning trace")


class GroundingBatchResult(BaseModel):
    """Batch grounding result from agent."""

    items: list[GroundingBatchItem] = Field(
        description="Batch of grounded criteria"
    )


# --- SAG Pipeline Schemas ---


class ExtractedTerm(BaseModel):
    """A clinical term extracted from criterion text for UMLS lookup."""

    term: str = Field(description="Clinical term to search in UMLS")
    snippet: str = Field(description="Text span this term was extracted from")
    relation: str | None = Field(
        default=None, description="Comparison operator: =, >, >=, <, <=, within"
    )
    value: str | None = Field(default=None, description="Numeric or categorical value")
    unit: str | None = Field(default=None, description="Unit of measurement")
    is_computed: bool = Field(
        default=False, description="True if this is a computed field like age"
    )
    computed_expression: str | None = Field(
        default=None, description="Expression for computed fields"
    )


class TermExtractionResult(BaseModel):
    """Result of extracting clinical terms from criterion text."""

    terms: list[ExtractedTerm] = Field(
        description="List of clinical terms to look up in UMLS"
    )
    logical_operator: str | None = Field(
        default=None, description="AND/OR relationship between terms"
    )


class UmlsCandidate(BaseModel):
    """A UMLS search result candidate."""

    term: str = Field(description="Original search term")
    snomed_code: str = Field(description="SNOMED CT code")
    display: str = Field(description="Concept display name")
    cui: str = Field(description="UMLS CUI")


class GroundingSelectionInput(BaseModel):
    """Input for the grounding selection step."""

    criterion_text: str = Field(description="Original criterion text")
    criterion_type: Literal["inclusion", "exclusion"] = Field(
        description="Criterion type"
    )
    extracted_terms: list[ExtractedTerm] = Field(
        description="Terms extracted in step 1"
    )
    umls_candidates: dict[str, list[UmlsCandidate]] = Field(
        description="UMLS search results keyed by term"
    )
