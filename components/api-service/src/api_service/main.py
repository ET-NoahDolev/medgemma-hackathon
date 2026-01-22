"""API service wireframe for the MedGemma hackathon demo."""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, List

from anyio import to_thread
from data_pipeline.download_protocols import extract_text_from_pdf
from dotenv import find_dotenv, load_dotenv
from extraction_service import pipeline as extraction_pipeline
from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from grounding_service import umls_client
from pydantic import BaseModel

from api_service.dependencies import get_storage
from api_service.storage import Criterion as StorageCriterion
from api_service.storage import Storage, init_db, reset_storage

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

# Try to import agent (optional dependency)
try:
    from grounding_service.agent import get_grounding_agent

    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False

# Configure MLflow tracking URI at module level to avoid filesystem backend warning
# Use absolute path to SQLite database in repo root
def _get_mlflow_tracking_uri() -> str:
    """Get the MLflow tracking URI using absolute path to SQLite database.

    Raises:
        RuntimeError: If .env file cannot be found to determine repo root.
    """
    # Find repo root by looking for .env file (find_dotenv walks up to find it)
    env_path = find_dotenv()
    if not env_path:
        raise RuntimeError(
            "Cannot determine repo root: .env file not found. "
            "Please ensure you're running from the repository root or have a .env file."
        )
    repo_root = Path(env_path).parent.absolute()
    db_path = repo_root / "mlflow.db"
    return f"sqlite:///{db_path}"


# Set environment variable before import so MLflow reads it during initialization
_mlflow_uri = _get_mlflow_tracking_uri()
os.environ.setdefault("MLFLOW_TRACKING_URI", _mlflow_uri)
try:
    import mlflow

    mlflow.set_tracking_uri(_mlflow_uri)
except ImportError:
    pass

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
    protocol_id: str, document_text: str, storage: Storage
) -> None:
    """Run extraction in background task (streaming)."""
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

    mlflow = _start_mlflow_run(protocol_id)

    count = 0
    try:
        # Prefer async extraction when model extraction is enabled to avoid
        # calling anyio.run() inside the running event loop thread.
        use_model = os.getenv("USE_MODEL_EXTRACTION", "true").lower() == "true"
        logger.info(
            f"Extraction: use_model={use_model}, MLflow active={mlflow is not None}"
        )
        if use_model and hasattr(extraction_pipeline, "extract_criteria_async"):
            logger.info("Extraction: Using async model extraction")
            items = await extraction_pipeline.extract_criteria_async(document_text)
            iterator = iter(items)
        else:
            iterator = extraction_pipeline.extract_criteria_stream(document_text)

        storage.update_protocol_status(
            protocol_id=protocol_id,
            progress_message="Extracting criteria…",
        )

        for item in iterator:
            storage.add_criterion_streaming(
                protocol_id=protocol_id,
                text=item.text,
                criterion_type=item.criterion_type,
                confidence=item.confidence,
            )
            count += 1
            if count == 1 or count % 5 == 0:
                storage.update_protocol_status(
                    protocol_id=protocol_id,
                    processed_count=count,
                    progress_message=f"Extracting criteria… ({count} found)",
                )

        storage.update_protocol_status(
            protocol_id=protocol_id,
            processing_status="completed",
            progress_message=f"Extraction completed ({count} criteria).",
        )
        _finish_mlflow_run(mlflow, count=count)
    except Exception:
        logger.exception("Extraction stream failed")
        storage.update_protocol_status(
            protocol_id=protocol_id,
            processing_status="failed",
            progress_message="Extraction failed.",
        )
        _finish_mlflow_run(mlflow, count=count, failed=True)


def _start_mlflow_run(protocol_id: str) -> Any | None:
    """Start an MLflow run if MLflow is installed."""
    try:
        import mlflow
    except ImportError:
        logger.debug("MLflow not available, skipping logging")
        return None

    try:
        # Use absolute path for mlflow.db to ensure consistency regardless of CWD.
        mlflow.set_tracking_uri(_get_mlflow_tracking_uri())
        mlflow.set_experiment("medgemma-extraction")
        mlflow.start_run(run_name=f"extract_{protocol_id}")
        active_run = mlflow.active_run()
        run_id = active_run.info.run_id if active_run else "unknown"
        logger.info(f"MLflow: Started run {run_id} for protocol {protocol_id}")
        return mlflow
    except Exception as e:
        logger.warning(
            f"MLflow: Failed to start run for protocol {protocol_id}: {e}",
            exc_info=True,
        )
        return None


def _finish_mlflow_run(mlflow: Any | None, *, count: int, failed: bool = False) -> None:
    """Finish an MLflow run, best-effort."""
    if mlflow is None:
        return
    try:
        mlflow.log_metric("criteria_count", count)
        if failed:
            mlflow.end_run(status="FAILED")
        else:
            mlflow.end_run()
    except Exception:
        logger.exception("MLflow logging failed")


@app.post("/v1/protocols/upload")
async def upload_protocol(
    file: UploadFile = File(...),
    auto_extract: bool = True,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    storage: Storage = Depends(get_storage),
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
            _run_extraction, protocol.id, protocol.document_text, storage
        )

    return ProtocolResponse(protocol_id=protocol.id, title=protocol.title)


@app.post("/v1/protocols/{protocol_id}/extract")
def extract_criteria(
    protocol_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    storage: Storage = Depends(get_storage),
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
        _run_extraction, protocol_id, protocol.document_text, storage
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


async def _try_ai_grounding(
    criterion_text: str,
    criterion_type: str,
    criterion_id: str,
    storage: Storage,
) -> GroundingResponse | None:
    """Try AI grounding and return result if successful, None otherwise."""
    try:
        agent = get_grounding_agent()
        result = await agent.ground(criterion_text, criterion_type)
        if not result.snomed_codes and not result.field_mappings:
            raise RuntimeError("AI grounding returned empty result")

        # Convert agent result to API response format
        response_candidates = []
        with umls_client.UmlsClient(api_key=_get_umls_api_key()) as client:
            for code in result.snomed_codes:
                # Try to get display name from UMLS by searching for the code
                candidates = client.search_snomed(code, limit=1)
                if candidates and candidates[0].code == code:
                    # Found exact match for the AI-provided code
                    response_candidates.append(
                        GroundingCandidateResponse(
                            code=candidates[0].code,
                            display=candidates[0].display,
                            ontology=candidates[0].ontology,
                            confidence=candidates[0].confidence,
                        )
                    )
                else:
                    # Code not found in UMLS - log warning and skip
                    logger.warning(
                        "AI-provided SNOMED code %s not found in UMLS, skipping",
                        code,
                    )

        field_mapping = None
        if result.field_mappings:
            mapping = result.field_mappings[0]
            field_mapping = FieldMappingResponse(
                field=mapping.field,
                relation=mapping.relation,
                value=mapping.value,
                confidence=mapping.confidence,
            )

        # Store SNOMED codes (only validated ones that made it into response)
        validated_codes = [c.code for c in response_candidates]
        storage.set_snomed_codes(
            criterion_id=criterion_id, snomed_codes=validated_codes
        )

        # If no candidates were found/validated, make it clear
        if not response_candidates:
            logger.warning(
                "AI grounding returned %d codes but none were validated in UMLS",
                len(result.snomed_codes),
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
            criterion.text, criterion.criterion_type, criterion_id, storage
        )
        if result is not None:
            return result

    # Fallback to baseline regex-based grounding
    return _baseline_grounding(criterion.text, criterion_id, storage)


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
