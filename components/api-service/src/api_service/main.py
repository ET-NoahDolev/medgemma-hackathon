"""API service wireframe for the MedGemma hackathon demo."""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from anyio import to_thread
from data_pipeline.download_protocols import extract_text_from_pdf
from extraction_service import pipeline as extraction_pipeline
from fastapi import Body, Depends, FastAPI, File, HTTPException, UploadFile
from grounding_service import umls_client
from pydantic import BaseModel

from api_service.dependencies import get_storage
from api_service.storage import Criterion as StorageCriterion
from api_service.storage import Storage, init_db, reset_storage


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
    """Initialize and teardown app state for the lifespan scope."""
    init_db()
    if not (os.getenv("UMLS_API_KEY") or os.getenv("GROUNDING_SERVICE_UMLS_API_KEY")):
        raise RuntimeError(
            "UMLS_API_KEY (or GROUNDING_SERVICE_UMLS_API_KEY) must be set "
            "for grounding-service"
        )
    yield


app = FastAPI(title="Gemma Hackathon API", version="0.1.0", lifespan=lifespan)
DEFAULT_MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024


def _max_upload_size_bytes() -> int:
    raw_value = os.getenv("API_SERVICE_MAX_UPLOAD_BYTES")
    if not raw_value:
        return DEFAULT_MAX_UPLOAD_SIZE_BYTES
    try:
        parsed = int(raw_value)
    except ValueError:
        return DEFAULT_MAX_UPLOAD_SIZE_BYTES
    if parsed <= 0:
        return DEFAULT_MAX_UPLOAD_SIZE_BYTES
    return parsed


MAX_UPLOAD_SIZE_BYTES = _max_upload_size_bytes()


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

    text: str | None = None
    criterion_type: str | None = None


class CriterionUpdateResponse(BaseModel):
    """Response payload after updating a criterion."""

    criterion_id: str
    status: str
    criterion: CriterionResponse


class GroundingCandidateResponse(BaseModel):
    """Response payload for grounding candidates."""

    code: str
    display: str
    ontology: str
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
    field_mapping: FieldMappingResponse | None


class HitlFeedbackRequest(BaseModel):
    """Payload for HITL feedback actions."""

    criterion_id: str
    action: str
    note: str | None = None


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


@app.post("/v1/protocols/upload")
async def upload_protocol(
    file: UploadFile = File(...),
    auto_extract: bool = True,
    storage: Storage = Depends(get_storage),
) -> ProtocolResponse:
    """Upload a PDF protocol file and create a protocol record."""
    filename = file.filename or ""
    if file.content_type != "application/pdf" or not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=415, detail="Unsupported media type; only PDF is allowed"
        )

    bytes_read = 0
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            bytes_read += len(chunk)
            if bytes_read > MAX_UPLOAD_SIZE_BYTES:
                tmp_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File too large")
            tmp.write(chunk)

    with tmp_path.open("rb") as handle:
        header = handle.read(4)
    if header != b"%PDF":
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    try:
        document_text = await to_thread.run_sync(extract_text_from_pdf, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not document_text:
        raise HTTPException(
            status_code=400, detail="No text could be extracted from the PDF"
        )

    title = filename.replace(".pdf", "").replace("_", " ").strip() or "Protocol"
    protocol = storage.create_protocol(title=title, document_text=document_text)

    if auto_extract:
        extracted = await to_thread.run_sync(
            extraction_pipeline.extract_criteria, protocol.document_text
        )
        storage.replace_criteria(protocol_id=protocol.id, extracted=extracted)

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
    payload: CriterionUpdateRequest | None = Body(default=None),
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

    with umls_client.UmlsClient(
        api_key=os.getenv("GROUNDING_SERVICE_UMLS_API_KEY")
        or os.getenv("UMLS_API_KEY")
    ) as client:
        candidates = client.search_snomed(criterion.text)
        field_mappings = umls_client.propose_field_mapping(criterion.text)

        if not candidates:
            storage.set_snomed_codes(criterion_id=criterion_id, snomed_codes=[])
            return GroundingResponse(
                criterion_id=criterion_id,
                candidates=[],
                field_mapping=None,
            )

        snomed_codes = [candidate.code for candidate in candidates]
        storage.set_snomed_codes(
            criterion_id=criterion_id,
            snomed_codes=snomed_codes,
        )

        response_candidates = [
            GroundingCandidateResponse(
                code=candidate.code,
                display=candidate.display,
                ontology=candidate.ontology,
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
