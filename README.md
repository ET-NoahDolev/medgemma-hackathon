# 🧬 MedGemma Hackathon

> **AI-powered clinical trial protocol analysis** — Extract, ground, and map inclusion/exclusion criteria with human-in-the-loop review

[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue?style=flat-square)](https://et-noahdolev.github.io/medgemma-hackathon/hackathon/docs/)
[![Python](https://img.shields.io/badge/python-3.12-blue?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Proprietary-red?style=flat-square)](LICENSE)

A comprehensive demo system for extracting atomic inclusion/exclusion criteria from clinical trial protocols, grounding them to SNOMED CT via the UMLS API, mapping to field/relation/value structures for EMR screening, and enabling nurse review through an intuitive HITL (Human-In-The-Loop) interface.

---

## 📚 Documentation

**📖 [View Full Documentation →](https://et-noahdolev.github.io/medgemma-hackathon/hackathon/docs/)**

The documentation includes:
- 📋 [Project Overview](https://et-noahdolev.github.io/medgemma-hackathon/hackathon/docs/overview/project/)
- 🏗️ [Architecture](https://et-noahdolev.github.io/medgemma-hackathon/hackathon/docs/overview/architecture/)
- 🚀 [Getting Started Guide](https://et-noahdolev.github.io/medgemma-hackathon/hackathon/docs/overview/getting-started/)
- 📡 [API Specification](https://et-noahdolev.github.io/medgemma-hackathon/hackathon/docs/api/api_spec/)
- 🧩 [Components Overview](https://et-noahdolev.github.io/medgemma-hackathon/hackathon/docs/components-overview/)

---

## 🎯 Project Goals

- ✅ **Extract** atomic criteria with evidence snippets from protocol documents
- 🔗 **Ground** criteria to SNOMED CT with ranked candidates and confidence scores
- 🗺️ **Map** criteria to field/relation/value structures (e.g., `demographics.age > 75`)
- 👩‍⚕️ **Enable** nurse review and corrections through HITL UI
- 📊 **Capture** edits for feedback loops and training data generation
- 🔌 **Integrate** with ElixirTrials platform workflows

---

## 🏗️ Architecture

This repository is organized as a **component-based monorepo**, where each service component operates independently while sharing common models and utilities.

### LangGraph Agent Architecture

The system uses **LangGraph ReAct agents** for extraction and grounding tasks. The architecture includes:

- **Agent Factory**: Centralized agent creation with lazy model loading and Jinja2 prompt rendering
- **Extraction Pipeline**: Hierarchical three-stage extraction (Page Filter → Paragraph Filter → Criteria Extraction)
- **Grounding Pipeline**: Single ReAct agent with UMLS tools for SNOMED grounding

📖 See the [LangGraph Architecture diagram](https://et-noahdolev.github.io/medgemma-hackathon/hackathon/docs/diagrams/langgraph-architecture/) for detailed information.

### System Flow

```
┌─────────────────┐
│ Protocol PDF    │
│ / Text          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Data Pipeline   │ ──► Protocol ingestion & parsing
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   API Service   │ ──► Orchestration & persistence
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌─────────┐ ┌──────────────┐
│Extraction│ │  Grounding   │ ──► UMLS API integration
│ Service  │ │   Service    │
└─────────┘ └──────────────┘
    │         │
    └────┬────┘
         │
         ▼
┌─────────────────┐
│   HITL UI       │ ◄──► Nurse review & corrections
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   Database      │ ──► Artifacts & training data
└─────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- **Python** 3.12+
- **UV** package manager ([installation guide](https://github.com/astral-sh/uv))
- **Node.js** 18+ (for HITL UI)
- **Docker** (optional, for local database)

### Installation

```bash
# Clone the repository
git clone https://github.com/elixirtrials/gemma-hackathon.git
cd gemma-hackathon

# Install dependencies
uv sync
```

### Running Services

#### 📖 Documentation

Build and serve the documentation locally:

```bash
# Build documentation
make docs-build

# Serve documentation (after building)
make docs-serve
```

Visit `http://localhost:8000` to view the docs.

#### 🔌 API Service

```bash
cd components/api-service
uv run uvicorn api_service.main:app --reload
```

API will be available at `http://localhost:8000` (FastAPI default).

#### 🔐 UMLS Configuration

Set these environment variables before running services that perform grounding:

- `UMLS_API_KEY` (required): Your UMLS API key from NLM UTS.
- `UMLS_BASE_URL` (optional): Defaults to `https://uts-ws.nlm.nih.gov/rest`.
- `UMLS_TIMEOUT_SECONDS` (optional): HTTP timeout in seconds (default 10).

The API service also respects `GROUNDING_SERVICE_UMLS_API_KEY` to override per-service deployments.

#### 📥 Data Pipeline

```bash
cd components/data-pipeline
uv run python -m data_pipeline.download_protocols
```

To load downloaded PDFs into the API database, use the loader:

```bash
# Single PDF
uv run python -m data_pipeline.loader --pdf data/protocols/example.pdf --api-url http://localhost:8000

# Bulk from manifest
uv run python -m data_pipeline.loader --manifest data/protocols/manifest.jsonl --limit 50
```

You can also upload a PDF directly to the API:

```bash
curl -X POST http://localhost:8000/v1/protocols/upload \
  -F "file=@data/protocols/example.pdf" \
  -F "auto_extract=true"
```

#### 🖥️ HITL UI

```bash
cd components/hitl-ui
npm install
npm run dev
```

UI will be available at `http://localhost:5173` (Vite default).

#### 📊 MLflow UI

To view MLflow experiment tracking, traces, and logged runs:

```bash
./scripts/start-mlflow-ui.sh
```

**Important:** Always use the script (`./scripts/start-mlflow-ui.sh`) rather than running `mlflow ui` directly. The script configures MLflow to use the SQLite database backend (`mlflow.db`) instead of the default filesystem backend.

MLflow UI will be available at `http://localhost:5000`.

**MLflow Tracing for LLM Observability:**
- The system uses **MLflow Tracing** for automatic LLM observability
- LangChain and LangGraph calls are automatically traced with token usage, latency, and execution flow
- View traces in the "Traces" tab in MLflow UI
- Runs are used for high-level extraction tracking
- See [MLflow Troubleshooting Guide](docs/mlflow-troubleshooting.md) for more details

The database contains experiments for:
- `medgemma-extraction` - Extraction service runs
- `medgemma-grounding` - Grounding service runs
- `medgemma-inference` - Agent inference runs

---

## 🧩 Components

| Component | Description | Tech Stack |
|-----------|-------------|------------|
| **`api-service`** | FastAPI endpoints and orchestration | FastAPI, Python |
| **`extraction-service`** | MedGemma-based extraction pipeline | Python, MedGemma |
| **`grounding-service`** | UMLS client and SNOMED grounding logic | Python, UMLS API |
| **`hitl-ui`** | React/Vite frontend for nurse review | React, TypeScript, Vite |
| **`data-pipeline`** | Protocol ingestion and parsing | Python |
| **`evaluation`** | Metrics calculation and reporting | Python |
| **`shared`** | Shared models and utilities | Python |

For detailed component documentation, see the [Components Overview](https://et-noahdolev.github.io/medgemma-hackathon/hackathon/docs/components-overview/) in the docs.

---

## 🛠️ Scripts

### Protocol Download Tool

The `scripts/download_protocol_sources.py` script downloads clinical trial protocol PDFs from multiple sources:

- **DAC (Data Access Committee)**: Protocol registry library
- **ClinicalTrials.gov**: Study protocols and documents
- **BMJ Open**: Protocol articles
- **JMIR Research Protocols**: Protocol publications

#### Usage Examples

```bash
# Download from all sources (default: 50 per source, 200 total)
python scripts/download_protocol_sources.py

# Download from specific sources
python scripts/download_protocol_sources.py --sources dac jmir

# Limit downloads per source
python scripts/download_protocol_sources.py --max-per-source 10 --max-total 30

# Custom output directory
python scripts/download_protocol_sources.py --output-dir data/my-protocols
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--output-dir` | Directory to store downloaded PDFs | `data/protocols` |
| `--sources` | Sources to download from (`dac`, `clinicaltrials`, `bmjopen`, `jmir`) | All sources |
| `--max-per-source` | Maximum PDFs per source | `50` |
| `--max-total` | Maximum PDFs overall | `200` |
| `--timeout` | Network timeout in seconds | `30` |
| `--sitemap-limit` | Number of sitemap files to scan per source | `2` |

The script creates a `manifest.jsonl` file tracking all download attempts with timestamps, URLs, file paths, and status (downloaded/failed).

### Other Utility Scripts

- **`scripts/create_component.sh`**: Initialize a new component with proper structure
- **`scripts/generate_components_overview.py`**: Generate the components overview documentation
- **`scripts/update_root_navigation.py`**: Update root mkdocs.yml navigation with discovered components

---

## 📊 Success Criteria

- **Extraction F1** ≥ 0.85
- **SNOMED Top-1 Accuracy** ≥ 0.80
- **Field/Relation/Value Mapping Quality** tracked (target TBD)
- **Nurse Acceptance Rate** ≥ 70%
- **Time per Protocol Reduction** ≥ 60% vs manual

---

## 📁 Repository Structure

```
gemma-hackathon/
├── components/          # Service components (API, extraction, grounding, UI, etc.)
│   ├── api-service/
│   ├── data-pipeline/
│   ├── extraction-service/
│   ├── grounding-service/
│   ├── hitl-ui/
│   ├── evaluation/
│   └── shared/
├── docs/                # MkDocs documentation
│   ├── overview/        # Project overview, architecture, getting started
│   ├── api/             # API specifications
│   ├── diagrams/        # Flow diagrams
│   └── phases/          # Hackathon phase plans
├── scripts/             # Utility scripts
├── data/                # Protocol data and manifests
├── instructions/        # Planning documents and references
└── site/                # Built documentation (generated)
```

---

## ⚠️ Disclaimer

**This is a demonstration project only. Not intended for clinical use.**

---

## 📄 License

**Proprietary** — ElixirTrials, Inc.

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to this project.

---

## 🔗 Links

- 📖 [Full Documentation](https://et-noahdolev.github.io/medgemma-hackathon/hackathon/docs/)
- 🐛 [Report Issues](https://github.com/elixirtrials/gemma-hackathon/issues)
- 💬 [Discussions](https://github.com/elixirtrials/gemma-hackathon/discussions)


## TODO:
 - Setup mlflow.genai.optimize_prompts() once we have HITL inputs so we can do this as a first pass optimization before fine tuning