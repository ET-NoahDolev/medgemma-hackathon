"""Pydantic schemas for model-based extraction."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExtractedCriterion(BaseModel):
    """Single criterion extracted by the model."""

    text: str = Field(..., description="Atomic criterion text")
    criterion_type: Literal["inclusion", "exclusion"] = Field(
        ..., description="Criterion type label"
    )
    confidence: float = Field(
        0.75, ge=0.0, le=1.0, description="Model confidence score"
    )


class ExtractionResult(BaseModel):
    """Structured extraction output."""

    criteria: list[ExtractedCriterion] = Field(
        default_factory=list, description="All extracted inclusion/exclusion criteria"
    )

