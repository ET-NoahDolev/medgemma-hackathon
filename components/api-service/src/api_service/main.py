"""API service wireframe for the MedGemma hackathon demo."""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Gemma Hackathon API", version="0.1.0")


class ProtocolCreateRequest(BaseModel):
    """Request payload for creating a protocol entry.

    Attributes:
        title: Human-readable trial title.
        document_text: Raw protocol text or extracted PDF text.

    Examples:
        >>> ProtocolCreateRequest(title="Trial A", document_text="Inclusion: ...")
        ProtocolCreateRequest(title='Trial A', document_text='Inclusion: ...')

    Notes:
        This model is a wireframe stub. Fields may expand to include metadata
        such as NCT ID, condition, phase, and source URLs.
    """

    title: str
    document_text: str


@app.post("/v1/protocols")
def create_protocol(payload: ProtocolCreateRequest) -> dict:
    """Create a protocol record and initial document entry.

    Args:
        payload: Metadata and text for the protocol.

    Returns:
        A minimal response containing the protocol identifier and title.

    Raises:
        ValueError: If required fields are missing or invalid.

    Examples:
        >>> create_protocol(ProtocolCreateRequest(title="Trial A", document_text="Inclusion: ..."))
        {'protocol_id': 'proto-1', 'title': 'Trial A'}

    Notes:
        This is a stub implementation. Persistence and validation will be
        added as part of the API hardening phase.
    """
    return {"protocol_id": "proto-1", "title": payload.title}


@app.post("/v1/protocols/{protocol_id}/extract")
def extract_criteria(protocol_id: str) -> dict:
    """Trigger extraction of atomic criteria for a protocol.

    Args:
        protocol_id: Identifier of the protocol to process.

    Returns:
        A status object describing the extraction trigger.

    Raises:
        ValueError: If the protocol is not found.

    Examples:
        >>> extract_criteria("proto-1")
        {'protocol_id': 'proto-1', 'status': 'queued'}

    Notes:
        In production, this endpoint will call the extraction service and
        persist criteria rows in the database.
    """
    return {"protocol_id": protocol_id, "status": "queued"}


@app.get("/v1/protocols/{protocol_id}/criteria")
def list_criteria(protocol_id: str) -> dict:
    """List criteria generated for a protocol.

    Args:
        protocol_id: Identifier of the protocol to retrieve criteria for.

    Returns:
        A response containing the protocol ID and a list of criteria.

    Raises:
        ValueError: If the protocol is not found.

    Examples:
        >>> list_criteria("proto-1")
        {'protocol_id': 'proto-1', 'criteria': []}

    Notes:
        This is currently a wireframe response. It will be backed by
        database results in the API service implementation.
    """
    return {"protocol_id": protocol_id, "criteria": []}


@app.patch("/v1/criteria/{criterion_id}")
def update_criterion(criterion_id: str) -> dict:
    """Update a single criterion or its metadata.

    Args:
        criterion_id: Identifier of the criterion to update.

    Returns:
        A minimal confirmation response.

    Raises:
        ValueError: If the criterion is not found or the update is invalid.

    Examples:
        >>> update_criterion("crit-1")
        {'criterion_id': 'crit-1', 'status': 'updated'}

    Notes:
        The final implementation will accept a PATCH payload with fields
        like text, criterion type, and evidence spans.
    """
    return {"criterion_id": criterion_id, "status": "updated"}


@app.post("/v1/criteria/{criterion_id}/ground")
def ground_criterion(criterion_id: str) -> dict:
    """Retrieve SNOMED candidates for a criterion.

    Args:
        criterion_id: Identifier of the criterion to ground.

    Returns:
        A response containing candidate SNOMED codes.

    Raises:
        ValueError: If the criterion is not found.

    Examples:
        >>> ground_criterion("crit-1")
        {'criterion_id': 'crit-1', 'candidates': []}

    Notes:
        This endpoint will call the grounding service and cache candidate
        codes for HITL review.
    """
    return {"criterion_id": criterion_id, "candidates": []}


@app.post("/v1/hitl/feedback")
def hitl_feedback() -> dict:
    """Record HITL feedback for criteria and SNOMED candidates.

    Returns:
        A confirmation that feedback was recorded.

    Raises:
        ValueError: If the feedback payload is invalid.

    Examples:
        >>> hitl_feedback()
        {'status': 'recorded'}

    Notes:
        The final version will accept a payload describing the nurse action
        (accept/reject/add code) and evidence rationale.
    """
    return {"status": "recorded"}
