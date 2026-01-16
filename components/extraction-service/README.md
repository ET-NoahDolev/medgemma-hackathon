# extraction-service

Wireframe extraction pipeline for MedGemma Task A. Produces atomic inclusion/exclusion criteria from protocol text.

## Responsibilities

- Segment protocol text into candidate criteria.
- Classify criteria as inclusion/exclusion.
- Return evidence snippets and confidence scores.

## Key Module

- `extraction_service/pipeline.py`

## Example Usage

```python
from extraction_service.pipeline import extract_criteria

criteria = extract_criteria("Inclusion: Age >= 18...")
for item in criteria:
    print(item.text, item.criterion_type, item.confidence)
```

## Tests

```bash
make check-all
```

## Notes

This component is a stub. It documents the intended API for wiring MedGemma LoRA adapters.
