"""API service wireframe for the MedGemma hackathon demo."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List

import anyio
from anyio import to_thread
from data_pipeline.download_protocols import extract_text_from_pdf
from dotenv import find_dotenv, load_dotenv
from extraction_service import pipeline as extraction_pipeline  # noqa: F401
from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from grounding_service import umls_client
from pydantic import BaseModel
from shared.mlflow_utils import configure_mlflow_once

from api_service.dependencies import get_storage
from api_service.ingestion import ingest_protocol_document_text
from api_service.storage import Criterion as StorageCriterion
from api_service.storage import Storage, init_db, reset_storage


def get_session_context(
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> dict[str, str | None]:
    """Extract session and user IDs from request headers.

    Returns:
        Dictionary with 'session_id' and 'user_id' keys.
    """
    return {"session_id": x_session_id, "user_id": x_user_id}

# Load .env from repo root (find_dotenv walks up to find it)
load_dotenv(find_dotenv())

# Configure logging level from environment or default to INFO
# This ensures MLflow logging messages are visible
# Note: uvicorn may have already set up logging, so we need to override it
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
try:
    log_level = getattr(logging, log_level_str, logging.INFO)
except AttributeError:
    log_level = logging.INFO

# Force reconfiguration of logging to ensure our level is used
# This overrides uvicorn's default configuration
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,  # Override any existing configuration (including uvicorn's)
)

# Set level for common loggers used by the application
# These may have been created before basicConfig, so set explicitly
logging.getLogger("api_service").setLevel(log_level)
logging.getLogger("extraction_service").setLevel(log_level)
logging.getLogger("grounding_service").setLevel(log_level)
logging.getLogger("inference").setLevel(log_level)
logging.getLogger("uvicorn").setLevel(log_level)
logging.getLogger("uvicorn.access").setLevel(log_level)
logging.getLogger("uvicorn.error").setLevel(log_level)

logger = logging.getLogger(__name__)

# Track background tasks for graceful shutdown
_background_tasks: set[asyncio.Task[None]] = set()

# Try to import agent (optional dependency)
try:
    from grounding_service.agent import get_grounding_agent

    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False

DEFAULT_MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024
# Expose for backward compatibility with tests
MAX_UPLOAD_SIZE_BYTES = DEFAULT_MAX_UPLOAD_SIZE_BYTES


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
    configure_mlflow_once("medgemma-extraction")
    # Validate required configuration
    api_key = os.getenv("GROUNDING_SERVICE_UMLS_API_KEY") or os.getenv("UMLS_API_KEY")
    if not api_key:
        raise RuntimeError("UMLS_API_KEY or GROUNDING_SERVICE_UMLS_API_KEY must be set")
    yield
    # Shutdown: cancel all background tasks
    logger.info("Shutting down: cancelling %d background tasks", len(_background_tasks))
    for task in _background_tasks:
        if not task.done():
            task.cancel()
    # Wait for tasks to complete cancellation (with timeout)
    if _background_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*_background_tasks, return_exceptions=True),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Some background tasks did not complete within timeout")
        except Exception:
            pass  # Ignore exceptions during shutdown
    logger.info("Shutdown complete")


def _get_umls_api_key() -> str:
    api_key = os.getenv("GROUNDING_SERVICE_UMLS_API_KEY") or os.getenv("UMLS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Grounding service not configured")
    return api_key


app = FastAPI(title="Gemma Hackathon API", version="0.1.0", lifespan=lifespan)

# CORS (UI integration)
# Defaults support local Vite dev servers. Override with comma-separated origins in env.
_cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
allow_origins = (
    [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else ["http://localhost:5173", "http://localhost:3000"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class CriterionDetailResponse(BaseModel):
    """Response payload for a detailed criterion."""

    id: str
    text: str
    text_snippet: str
    criterion_type: str
    criteria_type: str
    entity: str | None
    umls_concept: str | None
    umls_id: str | None
    snomed_code: str | None
    snomed_codes: List[str]
    calculated_by: str | None
    relation: str | None
    value: str | None
    unit: str | None
    confidence: float
    triplet_confidence: float | None
    grounding_confidence: float | None
    logical_operator: str | None = None
    grounding_terms: List[dict[str, object]] = []
    umls_mappings: List[dict[str, object]] = []
    hitl_status: str
    hitl_entity: str | None
    hitl_umls_concept: str | None
    hitl_umls_id: str | None
    hitl_snomed_code: str | None
    hitl_relation: str | None
    hitl_value: str | None
    hitl_unit: str | None
    hitl_approved_at: datetime | None
    hitl_approved_by: str | None


class CriteriaListResponse(BaseModel):
    """Response payload for listing criteria."""

    protocol_id: str
    criteria: List[CriterionDetailResponse]


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
    criterion: CriterionDetailResponse


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


class FieldMappingSuggestionRequest(BaseModel):
    """Request payload for field mapping suggestions."""

    criterion_text: str


class FieldMappingSuggestionResponse(BaseModel):
    """Response payload for field mapping suggestions."""

    suggestions: List[FieldMappingResponse]


class GroundingResponse(BaseModel):
    """Response payload for grounding a criterion."""

    criterion_id: str
    candidates: List[GroundingCandidateResponse]
    field_mapping: FieldMappingResponse | None


class HitlAction(str, Enum):
    """HITL action types."""

    accept = "accept"
    reject = "reject"
    edit = "edit"
    add_code = "add_code"
    remove_code = "remove_code"
    add_mapping = "add_mapping"
    remove_mapping = "remove_mapping"


class HitlFeedbackRequest(BaseModel):
    """Payload for HITL feedback actions."""

    criterion_id: str
    action: HitlAction
    snomed_code_added: str | None = None
    snomed_code_removed: str | None = None
    field_mapping_added: str | None = None
    field_mapping_removed: str | None = None
    note: str | None = None


class HitlApproveRequest(BaseModel):
    """Payload for HITL approval."""

    user: str
    note: str | None = None


class HitlRejectRequest(BaseModel):
    """Payload for HITL rejection."""

    user: str
    reason: str


class HitlEditMappingRequest(BaseModel):
    """Payload for HITL edits to extracted mappings."""

    user: str
    edits: dict[str, object]
    note: str | None = None


class HitlEditResponse(BaseModel):
    """Response for a single HITL edit."""

    id: str
    criterion_id: str
    action: HitlAction
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
    processing_status: str
    progress_message: str | None = None
    processed_count: int
    total_estimated: int


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
    processing_status: str
    progress_message: str | None = None
    processed_count: int
    total_estimated: int


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


async def _run_extraction(
    protocol_id: str,
    document_text: str,
    storage: Storage,
    session_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Run extraction in background task (streaming)."""
    # Generate a unique run ID for this extraction to group all traces
    run_id = str(uuid.uuid4())
    logger.info("Starting extraction run_id=%s protocol_id=%s", run_id, protocol_id)
    try:
        storage.update_protocol_status(
            protocol_id=protocol_id,
            processing_status="extracting",
            progress_message="Starting extraction…",
            processed_count=0,
        )
        # Clear existing criteria first to support re-runs.
        storage.update_protocol_status(
            protocol_id=protocol_id,
            progress_message="Clearing previous criteria…",
        )
        storage.replace_criteria(protocol_id=protocol_id, extracted=[])

        storage.update_protocol_status(
            protocol_id=protocol_id,
            progress_message="Extracting and grounding criteria…",
        )
        criteria = await ingest_protocol_document_text(
            protocol_id=protocol_id,
            document_text=document_text,
            storage=storage,
            umls_api_key=_get_umls_api_key(),
            session_id=session_id,
            user_id=user_id,
            run_id=run_id,
        )
        count = len(criteria)
        storage.update_protocol_status(
            protocol_id=protocol_id,
            processing_status="completed",
            processed_count=count,
            progress_message=f"Ingestion completed ({count} criteria).",
        )
    except asyncio.CancelledError:
        logger.info("Extraction task cancelled for protocol %s", protocol_id)
        storage.update_protocol_status(
            protocol_id=protocol_id,
            processing_status="failed",
            progress_message="Extraction cancelled.",
        )
        raise
    except Exception:
        logger.exception("Extraction stream failed")
        partial_count = storage.count_criteria(protocol_id)
        storage.update_protocol_status(
            protocol_id=protocol_id,
            processing_status="failed",
            processed_count=partial_count,
            progress_message=(
                f"Extraction failed ({partial_count} criteria saved)."
                if partial_count
                else "Extraction failed."
            ),
        )


def _run_extraction_sync(
    protocol_id: str,
    document_text: str,
    storage: Storage,
    session_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Run extraction from sync background tasks."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        anyio.run(
            _run_extraction,
            protocol_id,
            document_text,
            storage,
            session_id,
            user_id,
        )
        return

    # Create and track the task
    task = loop.create_task(
        _run_extraction(protocol_id, document_text, storage, session_id, user_id)
    )
    _background_tasks.add(task)
    # Remove task from set when it completes
    task.add_done_callback(_background_tasks.discard)


@app.post("/v1/protocols/upload")
async def upload_protocol(
    file: UploadFile = File(...),
    auto_extract: bool = True,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    storage: Storage = Depends(get_storage),
    session_context: dict[str, str | None] = Depends(get_session_context),
) -> ProtocolResponse:
    """Upload a PDF protocol file and create a protocol record.

    If auto_extract is True, extraction runs asynchronously in the background
    after the response is returned to avoid request timeouts for large PDFs.
    """
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
        storage.update_protocol_status(
            protocol_id=protocol.id,
            progress_message="Queued for extraction…",
        )
        # Run extraction in background to avoid blocking the response
        background_tasks.add_task(
            _run_extraction_sync,
            protocol.id,
            protocol.document_text,
            storage,
            session_context.get("session_id"),
            session_context.get("user_id"),
        )

    return ProtocolResponse(protocol_id=protocol.id, title=protocol.title)


@app.post("/v1/protocols/{protocol_id}/extract")
def extract_criteria(
    protocol_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    storage: Storage = Depends(get_storage),
    session_context: dict[str, str | None] = Depends(get_session_context),
) -> ExtractionResponse:
    """Trigger extraction of atomic criteria for a protocol.

    Extraction runs asynchronously in the background after the response is returned
    to avoid request timeouts for long documents.
    """
    protocol = storage.get_protocol(protocol_id)
    if protocol is None:
        raise HTTPException(status_code=404, detail="Protocol not found")

    storage.update_protocol_status(
        protocol_id=protocol_id,
        progress_message="Queued for extraction…",
    )
    # Run extraction in background to avoid blocking the response
    background_tasks.add_task(
        _run_extraction_sync,
        protocol_id,
        protocol.document_text,
        storage,
        session_context.get("session_id"),
        session_context.get("user_id"),
    )

    return ExtractionResponse(
        protocol_id=protocol_id, status="processing", criteria_count=0
    )


@app.get("/v1/protocols")
def list_protocols(
    skip: int = 0,
    limit: int = 20,
    storage: Storage = Depends(get_storage),
) -> ProtocolListResponse:
    """List all protocols with pagination."""
    if skip < 0 or limit <= 0 or limit > 100:
        raise HTTPException(status_code=400, detail="Invalid pagination parameters")

    protocols, total = storage.list_protocols(skip=skip, limit=limit)
    return ProtocolListResponse(
        protocols=[
            ProtocolListItem(
                protocol_id=protocol.id,
                title=protocol.title,
                nct_id=protocol.nct_id,
                condition=protocol.condition,
                phase=protocol.phase,
                processing_status=getattr(protocol, "processing_status", "pending"),
                progress_message=getattr(protocol, "progress_message", None),
                processed_count=getattr(protocol, "processed_count", 0),
                total_estimated=getattr(protocol, "total_estimated", 0),
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

    criteria_count = storage.count_criteria(protocol_id)

    return ProtocolDetailResponse(
        protocol_id=protocol.id,
        title=protocol.title,
        document_text=protocol.document_text,
        nct_id=protocol.nct_id,
        condition=protocol.condition,
        phase=protocol.phase,
        criteria_count=criteria_count,
        processing_status=getattr(protocol, "processing_status", "pending"),
        progress_message=getattr(protocol, "progress_message", None),
        processed_count=getattr(protocol, "processed_count", 0),
        total_estimated=getattr(protocol, "total_estimated", 0),
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


@app.post("/v1/criteria/suggest-mapping")
def suggest_field_mapping(
    payload: FieldMappingSuggestionRequest,
) -> FieldMappingSuggestionResponse:
    """Suggest field mappings for a criterion text.

    This endpoint uses the same logic as the grounding service to propose
    field/relation/value mappings, allowing frontend components to get
    suggestions without duplicating the regex logic.
    """
    if not payload.criterion_text.strip():
        raise HTTPException(
            status_code=400, detail="criterion_text cannot be empty"
        )

    field_mappings = umls_client.propose_field_mapping(payload.criterion_text)

    suggestions = [
        FieldMappingResponse(
            field=mapping.field,
            relation=mapping.relation,
            value=mapping.value,
            confidence=mapping.confidence,
        )
        for mapping in field_mappings
    ]

    return FieldMappingSuggestionResponse(suggestions=suggestions)


def _infer_field_from_snippet(snippet: str) -> str:
    """Infer field name from snippet content."""
    snippet_lower = snippet.lower()
    if "age" in snippet_lower:
        return "demographics.age"
    if "hba1c" in snippet_lower or "a1c" in snippet_lower:
        return "labs.hba1c"
    if "bmi" in snippet_lower or "body mass index" in snippet_lower:
        return "demographics.bmi"
    if "weight" in snippet_lower:
        return "demographics.weight"
    if "height" in snippet_lower:
        return "demographics.height"
    return "unknown"


def _extract_field_mapping_from_terms(terms: list) -> FieldMappingResponse | None:
    """Extract field mapping from first term with relation and value."""
    for term in terms:
        if term.relation and term.value:
            field = _infer_field_from_snippet(term.snippet)
            return FieldMappingResponse(
                field=field,
                relation=term.relation,
                value=term.value,
                confidence=term.confidence,
            )
    return None


def _validate_snomed_codes(
    snomed_codes: list[str], client: umls_client.UmlsClient
) -> list[GroundingCandidateResponse]:
    """Validate SNOMED codes against UMLS and return candidates."""
    response_candidates = []
    for code in snomed_codes:
        candidates = client.search_snomed(code, limit=1)
        if candidates and candidates[0].code == code:
            response_candidates.append(
                GroundingCandidateResponse(
                    code=candidates[0].code,
                    display=candidates[0].display,
                    ontology=candidates[0].ontology,
                    confidence=candidates[0].confidence,
                )
            )
        else:
            logger.warning(
                "AI-provided SNOMED code %s not found in UMLS, skipping", code
            )
    return response_candidates


async def _try_ai_grounding(
    criterion_text: str,
    criterion_type: str,
    criterion_id: str,
    storage: Storage,
    session_id: str | None = None,
    user_id: str | None = None,
) -> GroundingResponse | None:
    """Try AI grounding and return result if successful, None otherwise."""
    try:
        agent = get_grounding_agent()
        result = await agent.ground(
            criterion_text, criterion_type, session_id, user_id
        )
        if not result.terms:
            raise RuntimeError("AI grounding returned empty result")

        # Extract SNOMED codes from terms
        snomed_codes = [
            term.snomed_code for term in result.terms if term.snomed_code
        ]

        # Validate codes and convert to response format
        with umls_client.UmlsClient(api_key=_get_umls_api_key()) as client:
            response_candidates = _validate_snomed_codes(snomed_codes, client)

        # Extract field mapping
        field_mapping = _extract_field_mapping_from_terms(result.terms)

        # Store SNOMED codes (only validated ones)
        validated_codes = [c.code for c in response_candidates]
        storage.set_snomed_codes(
            criterion_id=criterion_id, snomed_codes=validated_codes
        )

        # Warn if no candidates validated
        if not response_candidates:
            logger.warning(
                "AI grounding returned %d codes but none were validated in UMLS",
                len(snomed_codes),
            )

        return GroundingResponse(
            criterion_id=criterion_id,
            candidates=response_candidates,
            field_mapping=field_mapping,
        )
    except Exception as e:
        logger.warning(
            "AI grounding failed for criterion %s: %s, falling back to baseline",
            criterion_id,
            e,
        )
        return None


def _baseline_grounding(
    criterion_text: str,
    criterion_id: str,
    storage: Storage,
) -> GroundingResponse:
    """Perform baseline regex-based grounding."""
    with umls_client.UmlsClient(api_key=_get_umls_api_key()) as client:
        candidates = client.search_snomed(criterion_text)
        field_mappings = umls_client.propose_field_mapping(criterion_text)

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


@app.post("/v1/criteria/{criterion_id}/ground")
async def ground_criterion(
    criterion_id: str,
    storage: Storage = Depends(get_storage),
    session_context: dict[str, str | None] = Depends(get_session_context),
) -> GroundingResponse:
    """Retrieve SNOMED candidates and field mappings for a criterion."""
    criterion = storage.get_criterion(criterion_id)
    if criterion is None:
        raise HTTPException(status_code=404, detail="Criterion not found")

    # Try AI grounding if enabled
    use_ai = os.getenv("USE_AI_GROUNDING", "false").lower() == "true"
    logger.info(f"Grounding: use_ai={use_ai}, AGENT_AVAILABLE={AGENT_AVAILABLE}")
    if use_ai and AGENT_AVAILABLE:
        result = await _try_ai_grounding(
            criterion.text,
            criterion.criterion_type,
            criterion_id,
            storage,
            session_context.get("session_id"),
            session_context.get("user_id"),
        )
        if result is not None:
            return result

    # Fallback to baseline regex-based grounding
    return _baseline_grounding(criterion.text, criterion_id, storage)


def _criterion_to_response(criterion: StorageCriterion) -> CriterionDetailResponse:
    snomed_code = criterion.snomed_codes[0] if criterion.snomed_codes else None

    # Extract UMLS mappings from grounding_terms
    umls_mappings = []
    for term in criterion.grounding_terms:
        if isinstance(term, dict):
            mapping = {
                "umls_concept": term.get("umls_concept"),
                "umls_id": term.get("umls_id"),
                "snomed_code": term.get("snomed_code"),
                "confidence": term.get(
                    "umls_confidence", term.get("grounding_confidence", 0.0)
                ),
            }
            # Only include if at least one UMLS field is present
            if mapping["umls_concept"] or mapping["umls_id"] or mapping["snomed_code"]:
                umls_mappings.append(mapping)

    return CriterionDetailResponse(
        id=criterion.id,
        text=criterion.text,
        text_snippet=criterion.text,
        criterion_type=criterion.criterion_type,
        criteria_type=criterion.criterion_type,
        entity=criterion.entity,
        umls_concept=criterion.umls_concept,
        umls_id=criterion.umls_id,
        snomed_code=snomed_code,
        snomed_codes=criterion.snomed_codes,
        calculated_by=criterion.computed_as,
        relation=criterion.relation,
        value=criterion.value,
        unit=criterion.unit,
        confidence=criterion.confidence,
        triplet_confidence=criterion.triplet_confidence,
        grounding_confidence=criterion.grounding_confidence,
        logical_operator=criterion.logical_operator,
        grounding_terms=criterion.grounding_terms,
        umls_mappings=umls_mappings,
        hitl_status=criterion.hitl_status,
        hitl_entity=criterion.hitl_entity,
        hitl_umls_concept=criterion.hitl_umls_concept,
        hitl_umls_id=criterion.hitl_umls_id,
        hitl_snomed_code=criterion.hitl_snomed_code,
        hitl_relation=criterion.hitl_relation,
        hitl_value=criterion.hitl_value,
        hitl_unit=criterion.hitl_unit,
        hitl_approved_at=criterion.hitl_approved_at,
        hitl_approved_by=criterion.hitl_approved_by,
    )


@app.post("/v1/hitl/feedback")
def hitl_feedback(
    payload: HitlFeedbackRequest | None = None,
    storage: Storage = Depends(get_storage),
) -> dict[str, str]:
    """Record HITL feedback for criteria, SNOMED candidates, and field mappings."""
    if payload is None:
        raise HTTPException(status_code=400, detail="Missing feedback payload")

    # Ensure criterion exists
    criterion = storage.get_criterion(payload.criterion_id)
    if criterion is None:
        raise HTTPException(status_code=404, detail="Criterion not found")
    if payload.action == HitlAction.add_code and not payload.snomed_code_added:
        raise HTTPException(
            status_code=400, detail="snomed_code_added is required for add_code"
        )
    if payload.action == HitlAction.remove_code and not payload.snomed_code_removed:
        raise HTTPException(
            status_code=400, detail="snomed_code_removed is required for remove_code"
        )
    if payload.action == HitlAction.add_mapping and not payload.field_mapping_added:
        raise HTTPException(
            status_code=400, detail="field_mapping_added is required for add_mapping"
        )
    if (
        payload.action == HitlAction.remove_mapping
        and not payload.field_mapping_removed
    ):
        raise HTTPException(
            status_code=400,
            detail="field_mapping_removed is required for remove_mapping",
        )
    storage.create_hitl_edit(
        criterion_id=payload.criterion_id,
        action=payload.action.value,
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


@app.post("/v1/criteria/{criterion_id}/approve")
def approve_criterion(
    criterion_id: str,
    payload: HitlApproveRequest,
    storage: Storage = Depends(get_storage),
) -> CriterionDetailResponse:
    """Approve a criterion and copy AI values into HITL fields."""
    criterion = storage.get_criterion(criterion_id)
    if criterion is None:
        raise HTTPException(status_code=404, detail="Criterion not found")

    snomed_code = criterion.snomed_codes[0] if criterion.snomed_codes else None
    updated = storage.update_criterion_hitl(
        criterion_id=criterion_id,
        updates={
            "hitl_status": "approved",
            "hitl_entity": criterion.entity,
            "hitl_relation": criterion.relation,
            "hitl_value": criterion.value,
            "hitl_unit": criterion.unit,
            "hitl_umls_concept": criterion.umls_concept,
            "hitl_umls_id": criterion.umls_id,
            "hitl_snomed_code": snomed_code,
            "hitl_approved_at": datetime.now(timezone.utc),
            "hitl_approved_by": payload.user,
        },
    )
    storage.create_hitl_edit(
        criterion_id=criterion_id,
        action=HitlAction.accept.value,
        note=payload.note,
    )

    if updated is None:
        raise HTTPException(status_code=500, detail="Failed to update criterion")
    return _criterion_to_response(updated)


@app.post("/v1/criteria/{criterion_id}/reject")
def reject_criterion(
    criterion_id: str,
    payload: HitlRejectRequest,
    storage: Storage = Depends(get_storage),
) -> CriterionDetailResponse:
    """Reject a criterion and mark HITL status."""
    criterion = storage.get_criterion(criterion_id)
    if criterion is None:
        raise HTTPException(status_code=404, detail="Criterion not found")

    updated = storage.update_criterion_hitl(
        criterion_id=criterion_id,
        updates={
            "hitl_status": "rejected",
            "hitl_approved_at": datetime.now(timezone.utc),
            "hitl_approved_by": payload.user,
        },
    )
    storage.create_hitl_edit(
        criterion_id=criterion_id,
        action=HitlAction.reject.value,
        note=payload.reason,
    )

    if updated is None:
        raise HTTPException(status_code=500, detail="Failed to update criterion")
    return _criterion_to_response(updated)


@app.patch("/v1/criteria/{criterion_id}/edit-mapping")
def edit_criterion_mapping(
    criterion_id: str,
    payload: HitlEditMappingRequest,
    storage: Storage = Depends(get_storage),
) -> CriterionDetailResponse:
    """Apply HITL edits to mapping fields."""
    criterion = storage.get_criterion(criterion_id)
    if criterion is None:
        raise HTTPException(status_code=404, detail="Criterion not found")

    updates = {
        "hitl_status": "edited",
        "hitl_approved_at": datetime.now(timezone.utc),
        "hitl_approved_by": payload.user,
    }
    for key, value in payload.edits.items():
        updates[f"hitl_{key}"] = value

    updated = storage.update_criterion_hitl(
        criterion_id=criterion_id,
        updates=updates,
    )
    storage.create_hitl_edit(
        criterion_id=criterion_id,
        action=HitlAction.edit.value,
        note=payload.note,
    )

    if updated is None:
        raise HTTPException(status_code=500, detail="Failed to update criterion")
    return _criterion_to_response(updated)


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
                action=HitlAction(edit.action),
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


@app.get("/health/umls")
def get_umls_health() -> dict[str, object]:
    """Check UMLS API health status."""
    api_key = _get_umls_api_key()
    if not api_key:
        return {
            "status": "unhealthy",
            "api_available": False,
            "last_error": "UMLS_API_KEY not configured",
        }

    try:
        with umls_client.UmlsClient(api_key=api_key) as client:
            health = client.check_health()
            return health
    except Exception as e:
        logger.error("Error checking UMLS health: %s", e)
        return {
            "status": "unhealthy",
            "api_available": False,
            "last_error": f"Error checking health: {str(e)}",
        }
