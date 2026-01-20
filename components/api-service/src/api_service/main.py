"""API service wireframe for the MedGemma hackathon demo."""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

from anyio import to_thread
from data_pipeline.download_protocols import extract_text_from_pdf
from dotenv import load_dotenv
from extraction_service import pipeline as extraction_pipeline
from fastapi import Body, Depends, FastAPI, File, HTTPException, UploadFile
from grounding_service import umls_client
from pydantic import BaseModel

from api_service.dependencies import get_storage
from api_service.storage import Criterion as StorageCriterion
from api_service.storage import Storage, init_db, reset_storage

DEFAULT_MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024
# Expose for backward compatibility with tests
MAX_UPLOAD_SIZE_BYTES = DEFAULT_MAX_UPLOAD_SIZE_BYTES

# Load environment variables from repo root .env (if present) safely.
_here = Path(__file__).resolve()
_repo_root = _here.parents[4] if len(_here.parents) >= 5 else _here.parents[-1]
_env_path = _repo_root / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


@dataclass(frozen=True)
class ApiConfig:
    """Configuration for the API service."""

    max_upload_bytes: int

    @staticmethod
    def from_env() -> "ApiConfig":
        """Create ApiConfig from environment variables."""
        raw_value = os.getenv("API_SERVICE_MAX_UPLOAD_BYTES")
        try:
            value = int(raw_value) if raw_value else MAX_UPLOAD_SIZE_BYTES
        except ValueError:
            value = MAX_UPLOAD_SIZE_BYTES
        if value <= 0:
            value = MAX_UPLOAD_SIZE_BYTES
        return ApiConfig(max_upload_bytes=value)


def get_config() -> ApiConfig:
    """Get the current API configuration."""
    return ApiConfig.from_env()


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
    """Initialize and teardown app state for the lifespan scope."""
    init_db()
    # Validate required configuration
    api_key = os.getenv("GROUNDING_SERVICE_UMLS_API_KEY") or os.getenv("UMLS_API_KEY")
    if not api_key:
        raise RuntimeError("UMLS_API_KEY or GROUNDING_SERVICE_UMLS_API_KEY must be set")
    yield


def _get_umls_api_key() -> str:
    api_key = os.getenv("GROUNDING_SERVICE_UMLS_API_KEY") or os.getenv("UMLS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Grounding service not configured")
    return api_key


app = FastAPI(title="Gemma Hackathon API", version="0.1.0", lifespan=lifespan)


class ProtocolCreateRequest(BaseModel):
    """Request payload for creating a protocol entry."""

    title: str
    document_text: str
    nct_id: str | None = None
    condition: str | None = None
    phase: str | None = None


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
    snomed_code_added: str | None = None
    snomed_code_removed: str | None = None
    field_mapping_added: str | None = None
    field_mapping_removed: str | None = None
    note: str | None = None


class HitlEditResponse(BaseModel):
    """Response for a single HITL edit."""

    id: str
    criterion_id: str
    action: str
    snomed_code_added: str | None
    snomed_code_removed: str | None
    field_mapping_added: str | None
    field_mapping_removed: str | None
    note: str | None
    created_at: datetime


class HitlEditsListResponse(BaseModel):
    """Response for listing HITL edits."""

    criterion_id: str
    edits: List[HitlEditResponse]


class ProtocolListItem(BaseModel):
    """Protocol summary for list view."""

    protocol_id: str
    title: str
    nct_id: str | None = None
    condition: str | None = None
    phase: str | None = None


class ProtocolListResponse(BaseModel):
    """Response for listing protocols."""

    protocols: List[ProtocolListItem]
    total: int
    skip: int
    limit: int


class ProtocolDetailResponse(BaseModel):
    """Response for protocol detail view."""

    protocol_id: str
    title: str
    document_text: str
    nct_id: str | None = None
    condition: str | None = None
    phase: str | None = None
    criteria_count: int


def _reset_state() -> None:
    reset_storage()


@app.post("/v1/protocols")
def create_protocol(
    payload: ProtocolCreateRequest,
    storage: Storage = Depends(get_storage),
) -> ProtocolResponse:
    """Create a protocol record and initial document entry."""
    protocol = storage.create_protocol(
        title=payload.title,
        document_text=payload.document_text,
        nct_id=payload.nct_id,
        condition=payload.condition,
        phase=payload.phase,
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
            if bytes_read > get_config().max_upload_bytes:
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


@app.get("/v1/protocols")
def list_protocols(
    skip: int = 0,
    limit: int = 20,
    storage: Storage = Depends(get_storage),
) -> ProtocolListResponse:
    """List all protocols with pagination."""
    protocols, total = storage.list_protocols(skip=skip, limit=limit)
    return ProtocolListResponse(
        protocols=[
            ProtocolListItem(
                protocol_id=protocol.id,
                title=protocol.title,
                nct_id=protocol.nct_id,
                condition=protocol.condition,
                phase=protocol.phase,
            )
            for protocol in protocols
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@app.get("/v1/protocols/{protocol_id}")
def get_protocol(
    protocol_id: str,
    storage: Storage = Depends(get_storage),
) -> ProtocolDetailResponse:
    """Get protocol details."""
    protocol = storage.get_protocol(protocol_id)
    if protocol is None:
        raise HTTPException(status_code=404, detail="Protocol not found")

    criteria_count = len(storage.list_criteria(protocol_id))

    return ProtocolDetailResponse(
        protocol_id=protocol.id,
        title=protocol.title,
        document_text=protocol.document_text,
        nct_id=protocol.nct_id,
        condition=protocol.condition,
        phase=protocol.phase,
        criteria_count=criteria_count,
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

    with umls_client.UmlsClient(api_key=_get_umls_api_key()) as client:
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
    if payload is None:
        raise HTTPException(status_code=400, detail="Missing feedback payload")
    allowed_actions = {
        "accept",
        "reject",
        "edit",
        "add_code",
        "remove_code",
        "add_mapping",
        "remove_mapping",
    }
    if payload.action not in allowed_actions:
        raise HTTPException(
            status_code=400, detail=f"Invalid action: {payload.action}"
        )
    if payload.action == "add_code" and not payload.snomed_code_added:
        raise HTTPException(
            status_code=400, detail="snomed_code_added is required for add_code"
        )
    if payload.action == "remove_code" and not payload.snomed_code_removed:
        raise HTTPException(
            status_code=400, detail="snomed_code_removed is required for remove_code"
        )
    if payload.action == "add_mapping" and not payload.field_mapping_added:
        raise HTTPException(
            status_code=400, detail="field_mapping_added is required for add_mapping"
        )
    if payload.action == "remove_mapping" and not payload.field_mapping_removed:
        raise HTTPException(
            status_code=400,
            detail="field_mapping_removed is required for remove_mapping",
        )
    storage.create_hitl_edit(
        criterion_id=payload.criterion_id,
        action=payload.action,
        snomed_code_added=payload.snomed_code_added,
        snomed_code_removed=payload.snomed_code_removed,
        field_mapping_added=payload.field_mapping_added,
        field_mapping_removed=payload.field_mapping_removed,
        note=payload.note,
    )

    if payload.snomed_code_added:
        storage.add_snomed_code(payload.criterion_id, payload.snomed_code_added)
    if payload.snomed_code_removed:
        storage.remove_snomed_code(payload.criterion_id, payload.snomed_code_removed)
    return {"status": "recorded"}


@app.get("/v1/criteria/{criterion_id}/edits")
def list_criterion_edits(
    criterion_id: str,
    storage: Storage = Depends(get_storage),
) -> HitlEditsListResponse:
    """List all HITL edits for a criterion."""
    edits = storage.list_hitl_edits(criterion_id)
    return HitlEditsListResponse(
        criterion_id=criterion_id,
        edits=[
            HitlEditResponse(
                id=edit.id,
                criterion_id=edit.criterion_id,
                action=edit.action,
                snomed_code_added=edit.snomed_code_added,
                snomed_code_removed=edit.snomed_code_removed,
                field_mapping_added=edit.field_mapping_added,
                field_mapping_removed=edit.field_mapping_removed,
                note=edit.note,
                created_at=edit.created_at,
            )
            for edit in edits
        ],
    )
