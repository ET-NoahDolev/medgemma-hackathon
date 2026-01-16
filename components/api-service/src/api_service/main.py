from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Gemma Hackathon API", version="0.1.0")


class ProtocolCreateRequest(BaseModel):
    title: str
    document_text: str


@app.post("/v1/protocols")
def create_protocol(payload: ProtocolCreateRequest) -> dict:
    return {"protocol_id": "proto-1", "title": payload.title}


@app.post("/v1/protocols/{protocol_id}/extract")
def extract_criteria(protocol_id: str) -> dict:
    return {"protocol_id": protocol_id, "status": "queued"}


@app.get("/v1/protocols/{protocol_id}/criteria")
def list_criteria(protocol_id: str) -> dict:
    return {"protocol_id": protocol_id, "criteria": []}


@app.patch("/v1/criteria/{criterion_id}")
def update_criterion(criterion_id: str) -> dict:
    return {"criterion_id": criterion_id, "status": "updated"}


@app.post("/v1/criteria/{criterion_id}/ground")
def ground_criterion(criterion_id: str) -> dict:
    return {"criterion_id": criterion_id, "candidates": []}


@app.post("/v1/hitl/feedback")
def hitl_feedback() -> dict:
    return {"status": "recorded"}
