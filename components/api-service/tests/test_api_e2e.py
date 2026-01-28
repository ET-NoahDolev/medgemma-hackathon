import io

import pytest
from fastapi.testclient import TestClient

from tests.constants import (
    EXTRACTED_TEXT,
    SNOMED_CODE,
)


# Minimal valid PDF (empty page)
_MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj "
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n"
    b"0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n166\n%%EOF"
)


@pytest.mark.e2e
def test_end_to_end_workflow(
    client: TestClient,
    fake_services: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mock the PDF extraction and MedGemma batch extraction
    async def mock_extract_criteria_from_pdf(**kwargs: object) -> object:
        from extraction_service.pdf_extractor import CriterionSnippet, PDFExtractionResult

        return PDFExtractionResult(
            criteria=[
                CriterionSnippet(
                    text="Age >= 18",
                    criterion_type="inclusion",
                    confidence=0.9,
                )
            ]
        )

    def mock_extract_triplets_batch(texts: list[str]) -> list[dict[str, str | None]]:
        return [{"entity": "age", "relation": ">=", "value": "18", "unit": "years"}]

    monkeypatch.setattr(
        "api_service.ingestion.extract_criteria_from_pdf",
        mock_extract_criteria_from_pdf,
    )
    monkeypatch.setattr(
        "api_service.ingestion.extract_triplets_batch",
        mock_extract_triplets_batch,
    )

    # Upload PDF (which auto-triggers extraction)
    upload_response = client.post(
        "/v1/protocols/upload",
        files={"file": ("test.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf")},
        params={"auto_extract": "false"},  # Don't auto-extract, we'll trigger manually
    )
    assert upload_response.status_code == 200
    protocol_id = upload_response.json()["protocol_id"]
    assert protocol_id.startswith("proto-")

    extract_response = client.post(f"/v1/protocols/{protocol_id}/extract")
    assert extract_response.status_code == 200
    # Extraction now runs in background, so status is "processing"
    assert extract_response.json()["status"] == "processing"

    list_response = client.get(f"/v1/protocols/{protocol_id}/criteria")
    assert list_response.status_code == 200
    criteria = list_response.json()["criteria"]
    assert criteria[0]["text"] == EXTRACTED_TEXT

    first_criterion_id = criteria[0]["id"]
    assert first_criterion_id.startswith("crit-")
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
    assert edits[0]["id"].startswith("edit-")

    client.post(
        "/v1/hitl/feedback",
        json={
            "criterion_id": first_criterion_id,
            "action": "add_code",
            "snomed_code_added": "371273006",
        },
    )

    updated_criteria = client.get(
        f"/v1/protocols/{protocol_id}/criteria"
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

    detail_response = client.get(f"/v1/protocols/{protocol_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["criteria_count"] >= 1
