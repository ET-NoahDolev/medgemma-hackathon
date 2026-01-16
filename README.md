# Gemma Hackathon

MedGemma hackathon demo for extracting atomic inclusion/exclusion criteria from trial protocols, grounding them to SNOMED via UBKG, and enabling nurse review in a HITL UI.

## Goals

- Extract atomic criteria with evidence snippets.
- Ground criteria to SNOMED with ranked candidates and confidence.
- Capture nurse edits for HITL feedback and training data.
- Provide a clear ElixirTrials integration story.

## Architecture Summary

The repository is a component-based monorepo. The API orchestrates data ingestion, extraction, grounding, and HITL feedback while persisting artifacts to the database.

```
protocol text/PDF -> data-pipeline -> API -> extraction-service
                                   -> grounding-service -> UBKG
HITL UI <------------------------------ API <-> database
```

## Quick Start

### Prerequisites

- Python 3.12
- UV package manager
- Node.js 18+ (for HITL UI)
- Docker (optional, for local DB)

### Install

```bash
uv sync
```

### Docs

```bash
make docs-build
make docs-serve
```

Visit `http://localhost:8000`.

### API Service (wireframe)

```bash
cd components/api-service
uv run uvicorn api_service.main:app --reload
```

### Data Pipeline (wireframe)

```bash
cd components/data-pipeline
uv run python -m data_pipeline.download_protocols
```

### HITL UI

```bash
cd components/hitl-ui
npm install
npm run dev
```

## Components

- `components/api-service` — FastAPI endpoints and orchestration.
- `components/extraction-service` — MedGemma extraction pipeline.
- `components/grounding-service` — UBKG client and grounding logic.
- `components/hitl-ui` — React/Vite HITL UI.
- `components/data-pipeline` — protocol ingestion.
- `components/evaluation` — metrics and reporting.
- `components/shared` — shared models and utilities.

## Documentation

See `docs/` for architecture, API spec, and phase plans. The hackathon plan is mirrored in `docs/overview/hackathon-plan.md`.

## Disclaimer

Demo only. Not for clinical use.

## License

Proprietary - ElixirTrials, Inc.
