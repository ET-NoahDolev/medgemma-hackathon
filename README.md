# Gemma Hackathon

MedGemma hackathon demo for extracting atomic inclusion/exclusion criteria from trial protocols, grounding them to SNOMED via UBKG, and enabling nurse review in a HITL UI.

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

### HITL UI

```bash
cd components/hitl-ui
npm install
npm run dev
```

## Project Structure

```
.
├── components/          # Service components (api, extraction, grounding, UI, etc.)
├── docs/                # MkDocs documentation
├── scripts/             # Build and utility scripts
├── instructions/        # Planning documents
├── mkdocs.yml           # MkDocs config
├── pyproject.toml       # Root Python config
├── Makefile             # Docs and component helpers
└── README.md
```

## Components

- `components/api-service` — FastAPI endpoints
- `components/extraction-service` — MedGemma extraction pipeline
- `components/grounding-service` — UBKG client and grounding logic
- `components/hitl-ui` — React/Vite HITL UI
- `components/data-pipeline` — protocol ingestion
- `components/evaluation` — metrics
- `components/shared` — shared models and utilities

## Documentation

See `docs/` for architecture and phase plans. The hackathon plan is mirrored in `docs/overview/hackathon-plan.md`.

## License

Proprietary - ElixirTrials, Inc.
