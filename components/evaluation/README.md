# evaluation

Metrics and reporting for extraction, grounding, and field/relation/value mapping quality.

## Responsibilities

- Compute extraction F1, SNOMED Top-1 accuracy, and field/relation/value mapping quality.
- Aggregate HITL acceptance metrics.

## Key Module

- `evaluation/metrics.py`

## Example Usage

```python
from evaluation.metrics import extraction_f1, snomed_top1_accuracy

f1 = extraction_f1(["age >= 18"], ["age >= 18"])
top1 = snomed_top1_accuracy(["372244006"], ["372244006"])
```

## Tests

```bash
make check-all
```
