import pytest
from fastapi.testclient import TestClient

from tests.constants import (
    CRITERION_ID,
    DOCUMENT_TEXT,
    EXTRACTED_TEXT,
    PROTOCOL_ID,
    PROTOCOL_TITLE,
    SNOMED_CODE,
)


@pytest.mark.e2e
def test_end_to_end_workflow(
    client: TestClient,
    fake_services: object,
) -> None:
    create_response = client.post(
        "/v1/protocols",
        json={"title": PROTOCOL_TITLE, "document_text": DOCUMENT_TEXT},
    )
    assert create_response.status_code == 200
    assert create_response.json()["protocol_id"] == PROTOCOL_ID

    extract_response = client.post(f"/v1/protocols/{PROTOCOL_ID}/extract")
    assert extract_response.status_code == 200
    assert extract_response.json()["status"] == "completed"

    list_response = client.get(f"/v1/protocols/{PROTOCOL_ID}/criteria")
    assert list_response.status_code == 200
    assert list_response.json()["criteria"][0]["text"] == EXTRACTED_TEXT

    update_response = client.patch(f"/v1/criteria/{CRITERION_ID}")
    assert update_response.status_code == 200
    assert update_response.json()["criterion"]["id"] == CRITERION_ID

    ground_response = client.post(f"/v1/criteria/{CRITERION_ID}/ground")
    assert ground_response.status_code == 200
    assert ground_response.json()["candidates"][0]["code"] == SNOMED_CODE

    feedback_response = client.post("/v1/hitl/feedback")
    assert feedback_response.status_code == 200
    assert feedback_response.json()["status"] == "recorded"
