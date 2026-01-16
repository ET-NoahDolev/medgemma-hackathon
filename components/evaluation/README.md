# evaluation

Metrics and reporting for extraction and grounding quality.

## Responsibilities

- Compute extraction F1 and SNOMED Top-1 accuracy.
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
