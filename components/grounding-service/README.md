# grounding-service

UMLS REST client and grounding helpers for Task B. Retrieves SNOMED candidates and field/relation/value mappings for each criterion.

## Responsibilities

- Query UMLS for SNOMED candidates.
- Propose field/relation/value mappings for screening.
- Return ranked candidates with display names and confidence scores.

## Key Module

- `grounding_service/umls_client.py`
- `grounding_service/agent.py` (LangGraph ReAct agent)

## Architecture

The grounding service uses a LangGraph ReAct agent with three tools:
1. **interpret_medical_text**: MedGemma-based medical text interpretation
2. **search_concepts_tool**: UMLS concept search for SNOMED candidates
3. **get_semantic_type_tool**: Semantic type lookup for UMLS concepts

See the [LangGraph Architecture diagram](../../docs/diagrams/langgraph-architecture.md) for detailed information.

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
