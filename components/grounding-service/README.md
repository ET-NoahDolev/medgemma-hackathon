# grounding-service

UBKG REST client and grounding helpers for Task B. Retrieves SNOMED candidates and field/relation/value mappings for each criterion.

## Responsibilities

- Query UBKG for SNOMED candidates.
- Propose field/relation/value mappings for screening.
- Return ranked candidates with display names and confidence scores.

## Key Module

- `grounding_service/ubkg_client.py`

## Example Usage

```python
from grounding_service.ubkg_client import UbkgClient

client = UbkgClient()
results = client.search_snomed("stage III melanoma")
print(results)
```

## Tests

```bash
make check-all
```

## Configuration (planned)

- `UBKG_BASE_URL` (default: `https://ubkg-api.xconsortia.org`)
- `UBKG_TIMEOUT_SECONDS`
