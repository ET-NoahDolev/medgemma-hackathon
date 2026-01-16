from fastapi.testclient import TestClient


def test_create_protocol_returns_payload(client: TestClient) -> None:
    response = client.post(
        "/v1/protocols",
        json={"title": "Trial A", "document_text": "Inclusion: Age >= 18."},
    )

    assert response.status_code == 200
    assert response.json() == {"protocol_id": "proto-1", "title": "Trial A"}
