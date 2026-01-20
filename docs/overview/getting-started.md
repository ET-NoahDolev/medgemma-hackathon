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
uv run python -m data_pipeline.download_protocols --manifest-path data/protocols/manifest.jsonl
```

To run the HITL UI:

```bash
cd components/hitl-ui
npm install
npm run dev
```

## Scripts

The repository includes utility scripts in the `scripts/` directory for common tasks.

### Protocol Download Tool

The protocol download tool (`scripts/download_protocol_sources.py`) downloads clinical trial protocol PDFs from multiple sources for use in the data pipeline.

**Basic Usage:**

```bash
# Download protocols from all sources (default settings)
python scripts/download_protocol_sources.py
```

**Advanced Usage:**

```bash
# Download from specific sources only
python scripts/download_protocol_sources.py --sources dac jmir

# Limit the number of downloads
python scripts/download_protocol_sources.py --max-per-source 10 --max-total 30

# Use a custom output directory
python scripts/download_protocol_sources.py --output-dir data/my-protocols
```

**Available Sources:**
- `dac`: Data Access Committee protocol registry
- `clinicaltrials`: ClinicalTrials.gov study protocols
- `bmjopen`: BMJ Open protocol articles
- `jmir`: JMIR Research Protocols

**Output:**
- PDFs are saved to `data/protocols/` (or specified directory) organized by source
- A `manifest.jsonl` file tracks all download attempts with metadata

**Command-Line Options:**
- `--output-dir PATH`: Directory for downloaded PDFs (default: `data/protocols`)
- `--sources SOURCE [SOURCE ...]`: Sources to download from (default: all)
- `--max-per-source N`: Maximum PDFs per source (default: 50)
- `--max-total N`: Maximum PDFs overall (default: 200)
- `--timeout SECONDS`: Network timeout (default: 30)
- `--sitemap-limit N`: Sitemap files to scan per source (default: 2)

### Development Scripts

- **`scripts/create_component.sh`**: Creates a new component with proper structure, dependencies, and documentation setup
- **`scripts/generate_components_overview.py`**: Auto-generates the components overview page from component metadata
- **`scripts/update_root_navigation.py`**: Updates the root mkdocs.yml navigation with all discovered components

## Testing

Each Python component includes a Makefile with linting, type-checking, and test targets:

```bash
cd components/api-service
make check-all
```
