# API Spec

The OpenAPI spec will live in this folder as `api_spec.yaml`.

Endpoints (minimal):

- `POST /v1/protocols`
- `POST /v1/protocols/{protocolId}/extract`
- `GET /v1/protocols/{protocolId}/criteria`
- `PATCH /v1/criteria/{criterionId}`
- `POST /v1/criteria/{criterionId}/ground` (SNOMED candidates + field/relation/value mapping)
- `POST /v1/hitl/feedback`
