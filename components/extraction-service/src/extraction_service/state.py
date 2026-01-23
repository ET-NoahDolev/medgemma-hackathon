"""State and structured finding models for extraction workflows."""

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from extraction_service.chunking import DocumentChunk


class CriterionTriplet(BaseModel):
    """Atomic entity/relation/value representation of a criterion."""

    entity: str = Field(..., description="Normalized entity, e.g., age, HbA1c.")
    relation: str = Field(
        ..., description="Relation, e.g., greater_than, equals, present, absent."
    )
    value: str | None = Field(
        default=None, description="Threshold/value when applicable, else None."
    )


class ChunkFinding(BaseModel):
    """Structured finding extracted from a single document chunk."""

    chunk_index: int = Field(..., ge=0)
    has_criteria: bool
    criterion_type: str | None = Field(
        default=None, description="inclusion/exclusion when applicable."
    )
    text: str = Field(default="", description="Full criterion text.")
    snippet: str = Field(
        default="", description="Shortest span capturing entity/relation/value."
    )
    triplet: CriterionTriplet | None = Field(
        default=None, description="Structured entity/relation/value."
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source_span: tuple[int, int] | None = Field(
        default=None, description="Character offsets in the current chunk."
    )


class DocumentProcessingState(TypedDict):
    """LangGraph state for document processing."""

    messages: Annotated[list[BaseMessage], add_messages]
    chunks: list[DocumentChunk]
    chunk_index: int
    total_chunks: int
    findings: Annotated[list[ChunkFinding], add]
    reasoning_steps: Annotated[list[str], add]
