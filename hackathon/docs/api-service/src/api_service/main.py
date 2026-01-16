"""API service wireframe for the MedGemma hackathon demo."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import List, Optional

from extraction_service import (
    pipeline as extraction_pipeline,  # type: ignore[import-not-found]
)
from fastapi import Body, Depends, FastAPI, HTTPException
from grounding_service import ubkg_client  # type: ignore[import-not-found]
from pydantic import BaseModel

from api_service.dependencies import get_storage
from api_service.storage import Criterion as StorageCriterion
from api_service.storage import Storage, init_db, reset_storage


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Initialize and teardown app state for the lifespan scope."""
    init_db()
    yield


app = FastAPI(title="Gemma Hackathon API", version="0.1.0", lifespan=lifespan)


class ProtocolCreateRequest(BaseModel):
    """Request payload for creating a protocol entry."""

    title: str
    document_text: str


class ProtocolResponse(BaseModel):
    """Response payload for a created protocol."""

    protocol_id: str
    title: str


class CriterionResponse(BaseModel):
    """Response payload for an extracted criterion."""

    id: str
    text: str
    criterion_type: str
    confidence: float
    snomed_codes: List[str]


class CriteriaListResponse(BaseModel):
    """Response payload for listing criteria."""

    protocol_id: str
    criteria: List[CriterionResponse]


class ExtractionResponse(BaseModel):
    """Response payload for extraction trigger."""

    protocol_id: str
    status: str
    criteria_count: int


class CriterionUpdateRequest(BaseModel):
    """Payload for updating a criterion."""

    text: Optional[str] = None
    criterion_type: Optional[str] = None


class CriterionUpdateResponse(BaseModel):
    """Response payload after updating a criterion."""

    criterion_id: str
    status: str
    criterion: CriterionResponse


class GroundingCandidateResponse(BaseModel):
    """Response payload for grounding candidates."""

    code: str
    display: str
    confidence: float


class FieldMappingResponse(BaseModel):
    """Response payload for a field mapping suggestion."""

    field: str
    relation: str
    value: str
    confidence: float


class GroundingResponse(BaseModel):
    """Response payload for grounding a criterion."""

    criterion_id: str
    candidates: List[GroundingCandidateResponse]
    field_mapping: Optional[FieldMappingResponse]


class HitlFeedbackRequest(BaseModel):
    """Payload for HITL feedback actions."""

    criterion_id: str
    action: str
    note: Optional[str] = None


def _reset_state() -> None:
    reset_storage()


@app.post("/v1/protocols")
def create_protocol(
    payload: ProtocolCreateRequest,
    storage: Storage = Depends(get_storage),
) -> ProtocolResponse:
    """Create a protocol record and initial document entry."""
    protocol = storage.create_protocol(
        title=payload.title, document_text=payload.document_text
    )
    return ProtocolResponse(protocol_id=protocol.id, title=protocol.title)


@app.post("/v1/protocols/{protocol_id}/extract")
def extract_criteria(
    protocol_id: str,
    storage: Storage = Depends(get_storage),
) -> ExtractionResponse:
    """Trigger extraction of atomic criteria for a protocol."""
    protocol = storage.get_protocol(protocol_id)
    if protocol is None:
        raise HTTPException(status_code=404, detail="Protocol not found")

    extracted = extraction_pipeline.extract_criteria(protocol.document_text)
    stored = storage.replace_criteria(
        protocol_id=protocol_id,
        extracted=extracted,
    )
    return ExtractionResponse(
        protocol_id=protocol_id, status="completed", criteria_count=len(stored)
    )


@app.get("/v1/protocols/{protocol_id}/criteria")
def list_criteria(
    protocol_id: str,
    storage: Storage = Depends(get_storage),
) -> CriteriaListResponse:
    """List criteria generated for a protocol."""
    protocol = storage.get_protocol(protocol_id)
    if protocol is None:
        raise HTTPException(status_code=404, detail="Protocol not found")

    criteria = [
        _criterion_to_response(criterion)
        for criterion in storage.list_criteria(protocol_id)
    ]
    return CriteriaListResponse(protocol_id=protocol_id, criteria=criteria)


@app.patch("/v1/criteria/{criterion_id}")
def update_criterion(
    criterion_id: str,
    payload: Optional[CriterionUpdateRequest] = Body(default=None),
    storage: Storage = Depends(get_storage),
) -> CriterionUpdateResponse:
    """Update a single criterion or its metadata."""
    updates = payload.model_dump(exclude_unset=True) if payload else {}
    criterion = storage.update_criterion(
        criterion_id=criterion_id,
        text=updates.get("text"),
        criterion_type=updates.get("criterion_type"),
    )
    if criterion is None:
        raise HTTPException(status_code=404, detail="Criterion not found")
    return CriterionUpdateResponse(
        criterion_id=criterion_id,
        status="updated",
        criterion=_criterion_to_response(criterion),
    )


@app.post("/v1/criteria/{criterion_id}/ground")
def ground_criterion(
    criterion_id: str,
    storage: Storage = Depends(get_storage),
) -> GroundingResponse:
    """Retrieve SNOMED candidates and field mappings for a criterion."""
    criterion = storage.get_criterion(criterion_id)
    if criterion is None:
        raise HTTPException(status_code=404, detail="Criterion not found")

    client = ubkg_client.UbkgClient()
    candidates = client.search_snomed(criterion.text)
    field_mappings = ubkg_client.propose_field_mapping(criterion.text)

    snomed_codes = [candidate.code for candidate in candidates]
    storage.set_snomed_codes(
        criterion_id=criterion_id,
        snomed_codes=snomed_codes,
    )

    response_candidates = [
        GroundingCandidateResponse(
            code=candidate.code,
            display=candidate.display,
            confidence=candidate.confidence,
        )
        for candidate in candidates
    ]

    field_mapping = None
    if field_mappings:
        suggestion = field_mappings[0]
        field_mapping = FieldMappingResponse(
            field=suggestion.field,
            relation=suggestion.relation,
            value=suggestion.value,
            confidence=suggestion.confidence,
        )

    return GroundingResponse(
        criterion_id=criterion_id,
        candidates=response_candidates,
        field_mapping=field_mapping,
    )


def _criterion_to_response(criterion: StorageCriterion) -> CriterionResponse:
    return CriterionResponse(
        id=criterion.id,
        text=criterion.text,
        criterion_type=criterion.criterion_type,
        confidence=criterion.confidence,
        snomed_codes=criterion.snomed_codes,
    )


@app.post("/v1/hitl/feedback")
def hitl_feedback(
    payload: HitlFeedbackRequest | None = None,
    storage: Storage = Depends(get_storage),
) -> dict[str, str]:
    """Record HITL feedback for criteria, SNOMED candidates, and field mappings."""
    _ = storage
    _ = payload
    return {"status": "recorded"}
