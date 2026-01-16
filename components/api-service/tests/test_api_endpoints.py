from fastapi.testclient import TestClient


def test_create_protocol_validation_error(client: TestClient) -> None:
    response = client.post("/v1/protocols", json={"title": "Trial A"})

    assert response.status_code == 422


def test_extract_criteria_returns_status(client: TestClient) -> None:
    response = client.post("/v1/protocols/proto-1/extract")

    assert response.status_code == 200
    assert response.json() == {"protocol_id": "proto-1", "status": "queued"}


def test_list_criteria_returns_empty(client: TestClient) -> None:
    response = client.get("/v1/protocols/proto-1/criteria")

    assert response.status_code == 200
    assert response.json() == {"protocol_id": "proto-1", "criteria": []}


def test_update_criterion_returns_status(client: TestClient) -> None:
    response = client.patch("/v1/criteria/crit-1")

    assert response.status_code == 200
    assert response.json() == {"criterion_id": "crit-1", "status": "updated"}


def test_ground_criterion_returns_candidates(client: TestClient) -> None:
    response = client.post("/v1/criteria/crit-1/ground")

    assert response.status_code == 200
    assert response.json() == {
        "criterion_id": "crit-1",
        "candidates": [],
        "field_mapping": None,
    }


def test_hitl_feedback_returns_recorded(client: TestClient) -> None:
    response = client.post("/v1/hitl/feedback")

    assert response.status_code == 200
    assert response.json() == {"status": "recorded"}
