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
