"""Pydantic schemas for structured agent output."""

from pydantic import BaseModel, Field


class UMLSConcept(BaseModel):
    """UMLS concept representation."""

    cui: str = Field(description="UMLS Concept Unique Identifier")
    name: str = Field(description="Preferred concept name")
    semantic_type: str = Field(description="UMLS semantic type (TUI)")


class FieldMappingResult(BaseModel):
    """Field mapping result with UMLS provenance."""

    field: str = Field(description="Target field path, e.g. demographics.age")
    relation: str = Field(description="Comparison operator: >, >=, <, <=, =")
    value: str = Field(description="Extracted value")
    confidence: float = Field(ge=0, le=1, description="Confidence score")
    umls_cui: str | None = Field(
        default=None, description="UMLS CUI provenance for this mapping"
    )


class GroundingResult(BaseModel):
    """Complete grounding result from agent."""

    snomed_codes: list[str] = Field(description="List of SNOMED CT codes")
    field_mappings: list[FieldMappingResult] = Field(
        description="List of field mapping suggestions"
    )
    reasoning: str = Field(description="Agent reasoning trace")
