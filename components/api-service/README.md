# api-service

FastAPI service that orchestrates protocol ingestion, extraction, grounding (SNOMED + field/relation/value), and HITL feedback. This is the entry point for the demo API.

## Responsibilities

- Expose REST endpoints for protocols, criteria, grounding (SNOMED + field mapping), and HITL edits.
- Validate request payloads and manage response shapes.
- Orchestrate calls to extraction and grounding components.

## Key Endpoints (wireframe)

- `POST /v1/protocols`
- `POST /v1/protocols/{protocol_id}/extract`
- `GET /v1/protocols/{protocol_id}/criteria`
- `PATCH /v1/criteria/{criterion_id}`
- `POST /v1/criteria/{criterion_id}/ground`
- `POST /v1/hitl/feedback`

## Running Locally

```bash
uv sync
uv run uvicorn api_service.main:app --reload
```

## Example Usage

```bash
curl -X POST http://localhost:8000/v1/protocols \
  -H "Content-Type: application/json" \
  -d '{"title":"Trial A","document_text":"Inclusion: ..."}'
```

## Tests

```bash
make check-all
```

## Configuration (planned)

- `DATABASE_URL` for persistence.
- `EXTRACTION_SERVICE_URL` for extraction orchestration.
- `GROUNDING_SERVICE_URL` for UMLS grounding.
