# Getting Started

## Prerequisites

- Python 3.12
- UV package manager
- Node.js 18+ (for HITL UI)
- Docker (optional, for local DB)

## Setup

```bash
uv sync
make docs-build
```

To serve docs locally:

```bash
make docs-serve
```

To run the API service (wireframe stub):

```bash
cd components/api-service
uv run uvicorn api_service.main:app --reload
```

To run the data pipeline stub:

```bash
cd components/data-pipeline
uv run python -m data_pipeline.download_protocols
```

To run the HITL UI:

```bash
cd components/hitl-ui
npm install
npm run dev
```

## Testing

Each Python component includes a Makefile with linting, type-checking, and test targets:

```bash
cd components/api-service
make check-all
```
