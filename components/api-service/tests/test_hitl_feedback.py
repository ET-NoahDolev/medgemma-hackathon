from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def setup_criterion(client: TestClient) -> tuple[str, str]:
    """Create protocol and extract criteria."""
    resp = client.post(
        "/v1/protocols",
        json={"title": "Test", "document_text": "Inclusion: Age >= 18"},
    )
    protocol_id = resp.json()["protocol_id"]
    client.post(f"/v1/protocols/{protocol_id}/extract")

    # Poll for criteria to appear (extraction runs in background)
    max_wait = 5.0  # seconds
    start_time = time.time()
    while time.time() - start_time < max_wait:
        criteria_resp = client.get(f"/v1/protocols/{protocol_id}/criteria")
        if criteria_resp.status_code == 200:
            criteria = criteria_resp.json().get("criteria", [])
            if criteria:
                return criteria[0]["id"], protocol_id
        time.sleep(0.1)  # Small delay between polls

    # If we get here, extraction didn't complete in time
    raise TimeoutError(
        f"Extraction did not complete within {max_wait}s for protocol {protocol_id}"
    )


class TestHitlFeedbackPersistence:
    def test_accept_action_persists(
        self, client: TestClient, setup_criterion: tuple[str, str]
    ) -> None:
        crit_id, _ = setup_criterion
        resp = client.post(
            "/v1/hitl/feedback",
            json={"criterion_id": crit_id, "action": "accept"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "recorded"

    def test_feedback_with_note(
        self, client: TestClient, setup_criterion: tuple[str, str]
    ) -> None:
        crit_id, _ = setup_criterion
        resp = client.post(
            "/v1/hitl/feedback",
            json={
                "criterion_id": crit_id,
                "action": "accept",
                "note": "Verified against protocol section 4.1",
            },
        )
        assert resp.status_code == 200


class TestHitlFeedbackSnomedUpdates:
    def test_add_snomed_code(
        self, client: TestClient, setup_criterion: tuple[str, str]
    ) -> None:
        crit_id, protocol_id = setup_criterion

        client.post(
            "/v1/hitl/feedback",
            json={
                "criterion_id": crit_id,
                "action": "add_code",
                "snomed_code_added": "371273006",
            },
        )

        criteria = client.get(f"/v1/protocols/{protocol_id}/criteria").json()[
            "criteria"
        ]
        crit = next(c for c in criteria if c["id"] == crit_id)
        assert "371273006" in crit["snomed_codes"]

    def test_remove_snomed_code(
        self, client: TestClient, setup_criterion: tuple[str, str]
    ) -> None:
        crit_id, protocol_id = setup_criterion

        client.post(
            "/v1/hitl/feedback",
            json={
                "criterion_id": crit_id,
                "action": "add_code",
                "snomed_code_added": "371273006",
            },
        )

        client.post(
            "/v1/hitl/feedback",
            json={
                "criterion_id": crit_id,
                "action": "remove_code",
                "snomed_code_removed": "371273006",
            },
        )

        criteria = client.get(f"/v1/protocols/{protocol_id}/criteria").json()[
            "criteria"
        ]
        crit = next(c for c in criteria if c["id"] == crit_id)
        assert "371273006" not in crit["snomed_codes"]


class TestHitlFeedbackFieldMapping:
    def test_add_field_mapping(
        self, client: TestClient, setup_criterion: tuple[str, str]
    ) -> None:
        crit_id, _ = setup_criterion

        # Use JSON format for field mapping
        field_mapping_json = '{"field":"demographics.age","relation":">=","value":"18"}'
        resp = client.post(
            "/v1/hitl/feedback",
            json={
                "criterion_id": crit_id,
                "action": "add_mapping",
                "field_mapping_added": field_mapping_json,
            },
        )
        assert resp.status_code == 200

    def test_add_field_mapping_legacy_format(
        self, client: TestClient, setup_criterion: tuple[str, str]
    ) -> None:
        """Test backward compatibility with pipe-delimited format."""
        crit_id, _ = setup_criterion

        resp = client.post(
            "/v1/hitl/feedback",
            json={
                "criterion_id": crit_id,
                "action": "add_mapping",
                "field_mapping_added": "demographics.age|>=|18",
            },
        )
        assert resp.status_code == 200


class TestHitlFeedbackHistory:
    def test_list_edits_for_criterion(
        self, client: TestClient, setup_criterion: tuple[str, str]
    ) -> None:
        crit_id, _ = setup_criterion

        client.post(
            "/v1/hitl/feedback",
            json={"criterion_id": crit_id, "action": "accept"},
        )
        client.post(
            "/v1/hitl/feedback",
            json={"criterion_id": crit_id, "action": "edit", "note": "Fixed typo"},
        )

        resp = client.get(f"/v1/criteria/{crit_id}/edits")
        assert resp.status_code == 200
        edits = resp.json()["edits"]
        assert len(edits) == 2

    def test_edits_have_timestamps(
        self, client: TestClient, setup_criterion: tuple[str, str]
    ) -> None:
        crit_id, _ = setup_criterion
        client.post(
            "/v1/hitl/feedback",
            json={"criterion_id": crit_id, "action": "accept"},
        )

        resp = client.get(f"/v1/criteria/{crit_id}/edits")
        assert "created_at" in resp.json()["edits"][0]
