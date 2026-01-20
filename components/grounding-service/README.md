# grounding-service

UMLS REST client and grounding helpers for Task B. Retrieves SNOMED candidates and field/relation/value mappings for each criterion.

## Responsibilities

- Query UMLS for SNOMED candidates.
- Propose field/relation/value mappings for screening.
- Return ranked candidates with display names and confidence scores.

## Key Module

- `grounding_service/umls_client.py`

## Example Usage

```python
from grounding_service.umls_client import UmlsClient

client = UmlsClient(api_key="your-umls-api-key")
results = client.search_snomed("stage III melanoma")
print(results)
```

## Tests

```bash
make check-all
```

## Configuration

- `UMLS_API_KEY` (required)
- `UMLS_BASE_URL` (default: `https://uts-ws.nlm.nih.gov/rest`)
- `UMLS_TIMEOUT_SECONDS`
