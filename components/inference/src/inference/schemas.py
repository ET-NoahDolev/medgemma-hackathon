"""Pydantic schemas for structured tool outputs.

These schemas ensure type-safe, validated JSON responses from MedGemma tools.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FieldMappingResult(BaseModel):
    """Structured output from extract_field_mapping tool."""

    field_name: str | None = Field(
        None, description="Field name (e.g., 'age', 'bmi', 'creatinine')"
    )
    relation_type: str | None = Field(
        None, description="Relation operator (e.g., '>=', '<', '==')"
    )
    value: str | None = Field(None, description="Field value")
    unit: str | None = Field(
        None, description="Unit of measurement (e.g., 'years', 'mg/dL')"
    )
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Confidence score"
    )


class CriterionClassificationResult(BaseModel):
    """Structured output from classify_criterion tool."""

    criterion_type: Literal["inclusion", "exclusion"] = Field(
        ..., description="Criterion type"
    )
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Confidence score"
    )
    reasoning: str = Field(..., description="Brief reasoning for classification")


class MedicalConceptsResult(BaseModel):
    """Structured output from identify_medical_concepts tool."""

    concepts: list[str] = Field(
        default_factory=list,
        description="List of medical terms to search in UMLS",
    )
    interpretation: str = Field(
        ..., description="Brief clinical interpretation"
    )
