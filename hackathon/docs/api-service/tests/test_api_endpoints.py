from fastapi.testclient import TestClient


def test_create_protocol_validation_error(client: TestClient) -> None:
    response = client.post("/v1/protocols", json={"title": "Trial A"})

    assert response.status_code == 422


def test_extract_criteria_populates_list(client: TestClient) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": "Trial A", "document_text": "Inclusion: Age >= 18."},
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
    assert criterion["text"] == "Age >= 18"
    assert criterion["criterion_type"] == "inclusion"
    assert criterion["confidence"] == 0.9
    assert criterion["snomed_codes"] == []


def test_update_criterion_returns_updated_value(client: TestClient) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": "Trial A", "document_text": "Inclusion: Age >= 18."},
    )
    protocol_id = create_response.json()["protocol_id"]
    client.post(f"/v1/protocols/{protocol_id}/extract")

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    criterion_id = list_response.json()["criteria"][0]["id"]

    response = client.patch(
        f"/v1/criteria/{criterion_id}",
        json={"text": "Age >= 21", "criterion_type": "inclusion"},
    )

    assert response.status_code == 200
    assert response.json()["criterion"]["text"] == "Age >= 21"


def test_ground_criterion_returns_candidates(client: TestClient) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": "Trial A", "document_text": "Inclusion: Age >= 18."},
    )
    protocol_id = create_response.json()["protocol_id"]
    client.post(f"/v1/protocols/{protocol_id}/extract")

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    criterion_id = list_response.json()["criteria"][0]["id"]

    response = client.post(f"/v1/criteria/{criterion_id}/ground")

    assert response.status_code == 200
    payload = response.json()
    assert payload["criterion_id"] == criterion_id
    assert payload["candidates"][0]["code"] == "371273006"
    assert payload["field_mapping"]["field"] == "demographics.age"


def test_hitl_feedback_returns_recorded(client: TestClient) -> None:
    response = client.post(
        "/v1/hitl/feedback",
        json={"criterion_id": "crit-1", "action": "accept"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "recorded"}
