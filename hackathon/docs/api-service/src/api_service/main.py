"""API service wireframe for the MedGemma hackathon demo."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Dict, List, Optional, cast

from extraction_service import (
    pipeline as extraction_pipeline,  # type: ignore[import-not-found]
)
from fastapi import Body, FastAPI, HTTPException
from grounding_service import ubkg_client  # type: ignore[import-not-found]
from pydantic import BaseModel
from shared import models as shared_models  # type: ignore[import-not-found]


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Initialize and teardown app state for the lifespan scope."""
    _reset_state()
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
    _ensure_state()
    app.state.protocol_counter = 0
    app.state.criterion_counter = 0
    app.state.protocols.clear()
    app.state.criteria.clear()
    app.state.protocol_criteria.clear()


def _ensure_state() -> None:
    if not hasattr(app.state, "protocol_counter"):
        app.state.protocol_counter = 0
        app.state.criterion_counter = 0
        app.state.protocols = cast(Dict[str, ProtocolCreateRequest], {})
        app.state.criteria = cast(Dict[str, shared_models.Criterion], {})
        app.state.protocol_criteria = cast(Dict[str, List[str]], {})


def _next_protocol_id() -> str:
    _ensure_state()
    app.state.protocol_counter += 1
    return f"proto-{app.state.protocol_counter}"


def _next_criterion_id() -> str:
    _ensure_state()
    app.state.criterion_counter += 1
    return f"crit-{app.state.criterion_counter}"


@app.post("/v1/protocols")
def create_protocol(payload: ProtocolCreateRequest) -> ProtocolResponse:
    """Create a protocol record and initial document entry."""
    _ensure_state()
    protocol_id = _next_protocol_id()
    app.state.protocols[protocol_id] = payload
    app.state.protocol_criteria[protocol_id] = []
    return ProtocolResponse(protocol_id=protocol_id, title=payload.title)


@app.post("/v1/protocols/{protocol_id}/extract")
def extract_criteria(protocol_id: str) -> ExtractionResponse:
    """Trigger extraction of atomic criteria for a protocol."""
    _ensure_state()
    if protocol_id not in app.state.protocols:
        raise HTTPException(status_code=404, detail="Protocol not found")

    protocol = app.state.protocols[protocol_id]
    extracted = extraction_pipeline.extract_criteria(protocol.document_text)

    for existing_id in app.state.protocol_criteria.get(protocol_id, []):
        app.state.criteria.pop(existing_id, None)

    stored_ids: List[str] = []
    for item in extracted:
        criterion_id = _next_criterion_id()
        criterion = shared_models.Criterion(
            id=criterion_id,
            text=item.text,
            criterion_type=item.criterion_type,
            confidence=item.confidence,
            snomed_codes=[],
        )
        app.state.criteria[criterion_id] = criterion
        stored_ids.append(criterion_id)

    app.state.protocol_criteria[protocol_id] = stored_ids
    return ExtractionResponse(
        protocol_id=protocol_id, status="completed", criteria_count=len(stored_ids)
    )


@app.get("/v1/protocols/{protocol_id}/criteria")
def list_criteria(protocol_id: str) -> CriteriaListResponse:
    """List criteria generated for a protocol."""
    _ensure_state()
    if protocol_id not in app.state.protocols:
        raise HTTPException(status_code=404, detail="Protocol not found")

    criteria_ids = app.state.protocol_criteria.get(protocol_id, [])
    criteria = [
        _criterion_to_response(app.state.criteria[criterion_id])
        for criterion_id in criteria_ids
    ]
    return CriteriaListResponse(protocol_id=protocol_id, criteria=criteria)


@app.patch("/v1/criteria/{criterion_id}")
def update_criterion(
    criterion_id: str, payload: Optional[CriterionUpdateRequest] = Body(default=None)
) -> CriterionUpdateResponse:
    """Update a single criterion or its metadata."""
    _ensure_state()
    if criterion_id not in app.state.criteria:
        raise HTTPException(status_code=404, detail="Criterion not found")

    criterion = app.state.criteria[criterion_id]
    if payload:
        updates = payload.model_dump(exclude_unset=True)
        if updates.get("text") is not None:
            criterion.text = updates["text"]
        if updates.get("criterion_type") is not None:
            criterion.criterion_type = updates["criterion_type"]
    app.state.criteria[criterion_id] = criterion
    return CriterionUpdateResponse(
        criterion_id=criterion_id,
        status="updated",
        criterion=_criterion_to_response(criterion),
    )


@app.post("/v1/criteria/{criterion_id}/ground")
def ground_criterion(criterion_id: str) -> GroundingResponse:
    """Retrieve SNOMED candidates and field mappings for a criterion."""
    _ensure_state()
    if criterion_id not in app.state.criteria:
        raise HTTPException(status_code=404, detail="Criterion not found")

    criterion = app.state.criteria[criterion_id]
    client = ubkg_client.UbkgClient()
    candidates = client.search_snomed(criterion.text)
    field_mappings = ubkg_client.propose_field_mapping(criterion.text)

    criterion.snomed_codes = [candidate.code for candidate in candidates]
    app.state.criteria[criterion_id] = criterion

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


def _criterion_to_response(criterion: shared_models.Criterion) -> CriterionResponse:
    return CriterionResponse(
        id=criterion.id,
        text=criterion.text,
        criterion_type=criterion.criterion_type,
        confidence=criterion.confidence,
        snomed_codes=criterion.snomed_codes,
    )


@app.post("/v1/hitl/feedback")
def hitl_feedback(payload: HitlFeedbackRequest | None = None) -> dict[str, str]:
    """Record HITL feedback for criteria, SNOMED candidates, and field mappings."""
    _ensure_state()
    _ = payload
    return {"status": "recorded"}
