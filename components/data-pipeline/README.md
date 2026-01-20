# data-pipeline

Protocol ingestion tools for ClinicalTrials.gov. Converts raw protocol documents into normalized records.

## Responsibilities

- Download or ingest protocol text/PDFs.
- Normalize and store protocol metadata.
- Emit data for extraction and grounding.

## Protocol Download

To download protocol PDFs from multiple sources (DAC, ClinicalTrials.gov, BMJ Open, JMIR), use the protocol download script in the root `scripts/` directory:

```bash
# From repository root
python scripts/download_protocol_sources.py

# With options
python scripts/download_protocol_sources.py --sources dac jmir --max-per-source 20
```

See the main [Getting Started](../overview/getting-started.md#scripts) documentation for full usage details.

## Entry Point

- `data_pipeline/download_protocols.py`
- `data_pipeline/loader.py`

## Running the Stub

```bash
# Ensure PDFs and manifest exist first
python scripts/download_protocol_sources.py --max-per-source 10

# Ingest downloaded PDFs
uv run python -m data_pipeline.download_protocols --manifest-path data/protocols/manifest.jsonl
```

## Load Into the API Database

Use the loader to import extracted PDFs into the API database.

```bash
# Single PDF
uv run python -m data_pipeline.loader --pdf data/protocols/example.pdf --api-url http://localhost:8000

# Bulk from manifest
uv run python -m data_pipeline.loader --manifest data/protocols/manifest.jsonl --limit 50

# Without auto-extraction
uv run python -m data_pipeline.loader --pdf data/protocols/example.pdf --no-extract
```

The API also exposes a PDF upload endpoint:

```bash
curl -X POST http://localhost:8000/v1/protocols/upload \
  -F "file=@data/protocols/example.pdf" \
  -F "auto_extract=true"
```

## Planned Outputs

- `protocols` table rows (`nct_id`, title, condition, phase).
- `documents` table rows for protocol text.
