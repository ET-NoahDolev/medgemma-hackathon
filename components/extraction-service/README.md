# extraction-service

Gemini-based extraction pipeline for MedGemma Task A. Produces atomic
inclusion/exclusion criteria from clinical trial protocol PDFs.

## Responsibilities

- Extract criteria directly from PDF attachments (Gemini).
- Batch MedGemma triplet extraction for entity/relation/value.

## Key Module

- `extraction_service/pdf_extractor.py`

## Architecture

The extraction service uses a two-stage pipeline:
1. **PDF Extraction**: Gemini extracts eligibility criteria directly from PDFs.
2. **Triplet Extraction**: MedGemma batches entity/relation/value extraction.

See the [LangGraph Architecture diagram](../../docs/diagrams/langgraph-architecture.md) for detailed information.

## Example Usage

```python
from extraction_service.pdf_extractor import extract_criteria_from_pdf

result = await extract_criteria_from_pdf(pdf_path=Path("protocol.pdf"))
for item in result.criteria:
    print(item.text, item.criterion_type, item.confidence)
```

## Configuration

The pipeline reads configuration from environment variables:

- `GEMINI_MODEL_NAME` (default: `gemini-2.5-pro`)
- `GCP_PROJECT_ID` (required for Vertex Gemini)
- `GCP_REGION` (default: `europe-west4`)
- `ENABLE_PDF_CHUNKING` (default: `false`) toggles PDF splitting for large documents.
- `PDF_CHUNK_MAX_PAGES` (default: `50`) maximum pages per chunk when enabled.
- `PDF_CHUNK_MAX_BYTES` (default: `10485760`) maximum bytes before chunking.
- `MEDGEMMA_BATCH_SIZE` (default: `10`) criteria per MedGemma triplet batch.

## Tests

```bash
make check-all
```
