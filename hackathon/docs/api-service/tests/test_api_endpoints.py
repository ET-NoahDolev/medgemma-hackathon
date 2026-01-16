from fastapi.testclient import TestClient

from tests.conftest import FakeExtractedCriterion
from tests.constants import (
    CRITERION_CONFIDENCE,
    CRITERION_TYPE,
    DOCUMENT_TEXT,
    EXTRACTED_TEXT,
    FIELD_MAPPING_FIELD,
    PROTOCOL_TITLE,
    SNOMED_CODE,
)


def test_create_protocol_validation_error(
    client: TestClient,
    fake_services: object,
) -> None:
    response = client.post("/v1/protocols", json={"title": PROTOCOL_TITLE})

    assert response.status_code == 422


def test_extract_criteria_populates_list(
    client: TestClient,
    fake_services: object,
) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]

    extract_response = client.post(f"/v1/protocols/{protocol_id}/extract")
    assert extract_response.status_code == 200
    assert extract_response.json()["status"] == "completed"

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    assert list_response.status_code == 200

    payload = list_response.json()
    assert payload["protocol_id"] == protocol_id
    assert len(payload["criteria"]) == 1

    criterion = payload["criteria"][0]
    assert criterion["text"] == EXTRACTED_TEXT
    assert criterion["criterion_type"] == CRITERION_TYPE
    assert criterion["confidence"] == CRITERION_CONFIDENCE
    assert criterion["snomed_codes"] == []


def test_update_criterion_returns_updated_value(
    client: TestClient,
    fake_services: object,
) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]
    client.post(f"/v1/protocols/{protocol_id}/extract")

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    criterion_id = list_response.json()["criteria"][0]["id"]

    response = client.patch(
        f"/v1/criteria/{criterion_id}",
        json={"text": "Age >= 21", "criterion_type": CRITERION_TYPE},
    )

    assert response.status_code == 200
    assert response.json()["criterion"]["text"] == "Age >= 21"


def test_ground_criterion_returns_candidates(
    client: TestClient,
    fake_services: object,
) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]
    client.post(f"/v1/protocols/{protocol_id}/extract")

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    criterion_id = list_response.json()["criteria"][0]["id"]

    response = client.post(f"/v1/criteria/{criterion_id}/ground")

    assert response.status_code == 200
    payload = response.json()
    assert payload["criterion_id"] == criterion_id
    assert payload["candidates"][0]["code"] == SNOMED_CODE
    assert payload["field_mapping"]["field"] == FIELD_MAPPING_FIELD


def test_hitl_feedback_returns_recorded(
    client: TestClient,
    fake_services: object,
) -> None:
    response = client.post(
        "/v1/hitl/feedback",
        json={"criterion_id": "crit-1", "action": "accept"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "recorded"}


def test_extract_replaces_existing_criteria(
    client: TestClient,
    fake_services: object,
) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]

    first_extract = client.post(f"/v1/protocols/{protocol_id}/extract")
    assert first_extract.status_code == 200

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    assert len(list_response.json()["criteria"]) == 1

    state = fake_services
    state.extracted = [
        FakeExtractedCriterion(
            text="Age >= 21",
            criterion_type=CRITERION_TYPE,
            confidence=0.91,
        ),
        FakeExtractedCriterion(
            text="BMI < 30",
            criterion_type=CRITERION_TYPE,
            confidence=0.75,
        ),
    ]

    second_extract = client.post(f"/v1/protocols/{protocol_id}/extract")
    assert second_extract.status_code == 200

    updated_list = client.get(f"/v1/protocols/{protocol_id}/criteria")
    payload = updated_list.json()
    assert payload["protocol_id"] == protocol_id
    assert len(payload["criteria"]) == 2


def test_ground_criterion_handles_no_mapping(
    client: TestClient,
    fake_services: object,
) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    protocol_id = create_response.json()["protocol_id"]
    client.post(f"/v1/protocols/{protocol_id}/extract")

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    criterion_id = list_response.json()["criteria"][0]["id"]

    state = fake_services
    state.field_mappings = []

    response = client.post(f"/v1/criteria/{criterion_id}/ground")
    assert response.status_code == 200
    payload = response.json()
    assert payload["field_mapping"] is None
