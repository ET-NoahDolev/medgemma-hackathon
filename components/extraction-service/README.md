# extraction-service

Hierarchical extraction pipeline for MedGemma Task A. Produces atomic
inclusion/exclusion criteria from clinical trial protocols.

## Responsibilities

- Filter pages for eligibility criteria content (Gemini).
- Filter paragraphs for criteria statements (Gemini).
- Extract atomic criteria with confidence scores (Gemini + MedGemma tools).

## Key Module

- `extraction_service/pipeline.py`

## Architecture

The extraction service uses a hierarchical three-stage LangGraph pipeline:
1. **Page Filter**: Identifies pages containing eligibility criteria (structured extractor)
2. **Paragraph Filter**: Narrows down to specific paragraphs (structured extractor)
3. **Criteria Extraction**: Extracts atomic criteria with entity/relation/value triplets (ReAct agent with tools)

See the [LangGraph Architecture diagram](../../docs/diagrams/langgraph-architecture.md) for detailed information.

## Example Usage

```python
from extraction_service.pipeline import extract_criteria

criteria = extract_criteria("Inclusion: Age >= 18...")
for item in criteria:
    print(item.text, item.criterion_type, item.confidence)
```

## Configuration

The pipeline reads configuration from environment variables:

- `GEMINI_MODEL_NAME` (default: `gemini-2.5-pro`)
- `GCP_PROJECT_ID` (required for Vertex Gemini)
- `GCP_REGION` (default: `europe-west4`)
- `EXTRACTION_MAX_PAGE_CHARS` (default: `4000`)
- `EXTRACTION_MAX_PAGES_PER_BATCH` (default: `6`)
- `EXTRACTION_MAX_PARAGRAPHS_PER_BATCH` (default: `10`)

## Tests

```bash
make check-all
```
