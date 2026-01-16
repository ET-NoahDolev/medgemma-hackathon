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

## Running the Stub

```bash
uv run python -m data_pipeline.download_protocols
```

## Planned Outputs

- `protocols` table rows (`nct_id`, title, condition, phase).
- `documents` table rows for protocol text.
