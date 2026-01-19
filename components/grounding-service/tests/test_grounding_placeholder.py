from unittest.mock import MagicMock, patch

import pytest

from grounding_service import umls_client


def test_snomed_candidate_dataclass() -> None:
    candidate = umls_client.SnomedCandidate(
        code="372244006",
        display="Malignant melanoma, stage III",
        ontology="SNOMEDCT_US",
        confidence=0.92,
    )

    assert candidate.code == "372244006"
    assert candidate.display == "Malignant melanoma, stage III"
    assert candidate.ontology == "SNOMEDCT_US"
    assert candidate.confidence == 0.92


def test_field_mapping_suggestion_dataclass() -> None:
    suggestion = umls_client.FieldMappingSuggestion(
        field="demographics.age",
        relation=">=",
        value="18",
        confidence=0.87,
    )

    assert suggestion.field == "demographics.age"
    assert suggestion.relation == ">="
    assert suggestion.value == "18"
    assert suggestion.confidence == 0.87


def test_umls_client_default_base_url() -> None:
    client = umls_client.UmlsClient(api_key="test-key")

    assert client.base_url == "https://uts-ws.nlm.nih.gov/rest"


def test_search_snomed_returns_list() -> None:
    mock_response = {
        "result": {
            "results": [
                {
                    "ui": "372244006",
                    "name": "Malignant melanoma, stage III",
                    "rootSource": "SNOMEDCT_US",
                }
            ]
        }
    }

    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            json=lambda: mock_response,
            status_code=200,
            raise_for_status=lambda: None,
        )
        client = umls_client.UmlsClient(api_key="test-key")
        results = client.search_snomed("stage III melanoma")

    assert isinstance(results, list)
    assert results[0].code == "372244006"


def test_propose_field_mapping_returns_list() -> None:
    suggestions = umls_client.propose_field_mapping("Age >= 75 years")

    assert isinstance(suggestions, list)
    assert suggestions[0].field == "demographics.age"
    assert suggestions[0].relation == ">="
    assert suggestions[0].value == "75"


def test_search_snomed_raises_on_empty_query() -> None:
    client = umls_client.UmlsClient(api_key="test-key")

    with pytest.raises(ValueError):
        client.search_snomed("")
