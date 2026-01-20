import pytest
from fastapi.testclient import TestClient

from api_service.main import app
from api_service.storage import reset_storage


@pytest.fixture()
def client() -> TestClient:
    reset_storage()
    return TestClient(app)


class TestListProtocols:
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/v1/protocols")
        assert resp.status_code == 200
        assert resp.json()["protocols"] == []

    def test_list_returns_protocols(self, client: TestClient) -> None:
        client.post(
            "/v1/protocols",
            json={"title": "Trial 1", "document_text": "Text 1"},
        )
        client.post(
            "/v1/protocols",
            json={"title": "Trial 2", "document_text": "Text 2"},
        )

        resp = client.get("/v1/protocols")
        assert len(resp.json()["protocols"]) == 2

    def test_list_pagination(self, client: TestClient) -> None:
        for i in range(15):
            client.post(
                "/v1/protocols",
                json={"title": f"Trial {i}", "document_text": f"Text {i}"},
            )

        resp = client.get("/v1/protocols?skip=0&limit=10")
        assert len(resp.json()["protocols"]) == 10

        resp = client.get("/v1/protocols?skip=10&limit=10")
        assert len(resp.json()["protocols"]) == 5


class TestGetProtocol:
    def test_get_protocol_detail(self, client: TestClient) -> None:
        create_resp = client.post(
            "/v1/protocols",
            json={
                "title": "Melanoma Trial",
                "document_text": "Inclusion: Age >= 18",
                "nct_id": "NCT12345678",
                "condition": "Melanoma",
                "phase": "Phase 2",
            },
        )
        protocol_id = create_resp.json()["protocol_id"]

        resp = client.get(f"/v1/protocols/{protocol_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Melanoma Trial"
        assert data["nct_id"] == "NCT12345678"

    def test_get_protocol_not_found(self, client: TestClient) -> None:
        resp = client.get("/v1/protocols/nonexistent")
        assert resp.status_code == 404

    def test_get_protocol_includes_criteria_count(self, client: TestClient) -> None:
        create_resp = client.post(
            "/v1/protocols",
            json={
                "title": "Trial",
                "document_text": "Inclusion: Age >= 18. Exclusion: Pregnant.",
            },
        )
        protocol_id = create_resp.json()["protocol_id"]
        client.post(f"/v1/protocols/{protocol_id}/extract")

        resp = client.get(f"/v1/protocols/{protocol_id}")
        assert "criteria_count" in resp.json()
        assert resp.json()["criteria_count"] >= 1
