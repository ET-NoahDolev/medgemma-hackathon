# shared

Shared data models and schemas used by API services and the UI.

## Responsibilities

- Define canonical data structures for protocols, criteria, groundings, and field/relation/value mappings.
- Keep type definitions synchronized across services.

## Key Module

- `shared/models.py`

## Example Usage

```python
from shared.models import Criterion

criterion = Criterion(
    id="crit-1",
    text="Age >= 18 years",
    criterion_type="inclusion",
    confidence=0.92,
    snomed_codes=["371273006"],
)
```

## Tests

```bash
make check-all
```
