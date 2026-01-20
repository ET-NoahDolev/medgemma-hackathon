import pytest
from fastapi.testclient import TestClient

from tests.constants import (
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
        json={
            "title": PROTOCOL_TITLE,
            "document_text": DOCUMENT_TEXT,
            "nct_id": "NCT99999999",
            "condition": "Cancer",
            "phase": "Phase 2",
        },
    )
    assert create_response.status_code == 200
    assert create_response.json()["protocol_id"] == PROTOCOL_ID

    extract_response = client.post(f"/v1/protocols/{PROTOCOL_ID}/extract")
    assert extract_response.status_code == 200
    assert extract_response.json()["status"] == "completed"

    list_response = client.get(f"/v1/protocols/{PROTOCOL_ID}/criteria")
    assert list_response.status_code == 200
    criteria = list_response.json()["criteria"]
    assert criteria[0]["text"] == EXTRACTED_TEXT

    first_criterion_id = criteria[0]["id"]
    ground_response = client.post(f"/v1/criteria/{first_criterion_id}/ground")
    assert ground_response.status_code == 200
    assert ground_response.json()["candidates"][0]["code"] == SNOMED_CODE

    feedback_response = client.post(
        "/v1/hitl/feedback",
        json={
            "criterion_id": first_criterion_id,
            "action": "accept",
            "note": "Verified correct",
        },
    )
    assert feedback_response.status_code == 200
    assert feedback_response.json()["status"] == "recorded"

    edits_response = client.get(f"/v1/criteria/{first_criterion_id}/edits")
    assert edits_response.status_code == 200
    edits = edits_response.json()["edits"]
    assert len(edits) == 1
    assert edits[0]["action"] == "accept"

    client.post(
        "/v1/hitl/feedback",
        json={
            "criterion_id": first_criterion_id,
            "action": "add_code",
            "snomed_code_added": "371273006",
        },
    )

    updated_criteria = client.get(
        f"/v1/protocols/{PROTOCOL_ID}/criteria"
    ).json()["criteria"]
    updated_criterion = next(
        criterion
        for criterion in updated_criteria
        if criterion["id"] == first_criterion_id
    )
    assert "371273006" in updated_criterion["snomed_codes"]

    protocols_response = client.get("/v1/protocols?skip=0&limit=10")
    assert protocols_response.status_code == 200
    assert len(protocols_response.json()["protocols"]) >= 1

    detail_response = client.get(f"/v1/protocols/{PROTOCOL_ID}")
    assert detail_response.status_code == 200
    assert detail_response.json()["criteria_count"] >= 1
