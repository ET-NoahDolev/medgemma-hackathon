from grounding_service import ubkg_client


def test_ubkg_candidate_dataclass() -> None:
    candidate = ubkg_client.UbkgCandidate(
        code="372244006",
        display="Malignant melanoma, stage III",
        ontology="SNOMED CT",
        confidence=0.92,
    )

    assert candidate.code == "372244006"
    assert candidate.display == "Malignant melanoma, stage III"
    assert candidate.ontology == "SNOMED CT"
    assert candidate.confidence == 0.92


def test_field_mapping_suggestion_dataclass() -> None:
    suggestion = ubkg_client.FieldMappingSuggestion(
        field="demographics.age",
        relation=">=",
        value="18",
        confidence=0.87,
    )

    assert suggestion.field == "demographics.age"
    assert suggestion.relation == ">="
    assert suggestion.value == "18"
    assert suggestion.confidence == 0.87


def test_ubkg_client_default_base_url() -> None:
    client = ubkg_client.UbkgClient()

    assert client.base_url == "https://ubkg-api.xconsortia.org"


def test_search_snomed_returns_list() -> None:
    client = ubkg_client.UbkgClient()

    results = client.search_snomed("stage III melanoma")

    assert isinstance(results, list)
    assert results == []


def test_propose_field_mapping_returns_list() -> None:
    suggestions = ubkg_client.propose_field_mapping("Age >= 75 years")

    assert isinstance(suggestions, list)
    assert suggestions == []
