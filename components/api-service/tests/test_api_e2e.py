import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
def test_end_to_end_workflow(client: TestClient) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": "Trial A", "document_text": "Inclusion: Age >= 18."},
    )
    assert create_response.status_code == 200
    assert create_response.json()["protocol_id"] == "proto-1"

    extract_response = client.post("/v1/protocols/proto-1/extract")
    assert extract_response.status_code == 200
    assert extract_response.json()["status"] == "queued"

    list_response = client.get("/v1/protocols/proto-1/criteria")
    assert list_response.status_code == 200
    assert list_response.json()["criteria"] == []

    update_response = client.patch("/v1/criteria/crit-1")
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "updated"

    ground_response = client.post("/v1/criteria/crit-1/ground")
    assert ground_response.status_code == 200
    assert ground_response.json()["candidates"] == []

    feedback_response = client.post("/v1/hitl/feedback")
    assert feedback_response.status_code == 200
    assert feedback_response.json()["status"] == "recorded"
