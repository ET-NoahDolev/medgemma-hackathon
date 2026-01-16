# data-pipeline

Protocol ingestion tools for ClinicalTrials.gov. Converts raw protocol documents into normalized records.

## Responsibilities

- Download or ingest protocol text/PDFs.
- Normalize and store protocol metadata.
- Emit data for extraction and grounding.

## Entry Point

- `data_pipeline/download_protocols.py`

## Running the Stub

```bash
uv run python -m data_pipeline.download_protocols
```

## Planned Outputs

- `protocols` table rows (`nct_id`, title, condition, phase).
- `documents` table rows for protocol text.
