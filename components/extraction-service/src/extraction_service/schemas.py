"""Pydantic schemas for model-based extraction."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PageFilterResult(BaseModel):
    """Structured output for page-level filtering."""

    pages: list[int] = Field(
        default_factory=list,
        description="Page numbers that contain eligibility criteria.",
    )


class ParagraphFilterResult(BaseModel):
    """Structured output for paragraph-level filtering."""

    paragraph_indices: list[int] = Field(
        default_factory=list,
        description="Paragraph indices that contain eligibility criteria.",
    )


class ExtractedCriterion(BaseModel):
    """Single criterion extracted by the model."""

    text: str = Field(..., description="Atomic criterion text")
    criterion_type: Literal["inclusion", "exclusion"] = Field(
        ..., description="Criterion type label"
    )
    confidence: float = Field(
        0.75, ge=0.0, le=1.0, description="Model confidence score"
    )
    entity: str | None = Field(None, description="Primary entity, if extracted")
    relation: str | None = Field(None, description="Relation/operator, if extracted")
    value: str | None = Field(None, description="Value, if extracted")
    unit: str | None = Field(None, description="Unit, if extracted")


class ExtractionResult(BaseModel):
    """Structured extraction output."""

    criteria: list[ExtractedCriterion] = Field(
        default_factory=list, description="All extracted inclusion/exclusion criteria"
    )

