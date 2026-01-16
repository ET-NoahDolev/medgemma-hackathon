from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from data_pipeline.download_protocols import (
    ProtocolRecord,
    emit_records,
    fetch_from_clinicaltrials,
)


@pytest.fixture()
def mock_ct_response() -> dict:
    return {
        "studies": [
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT12345678",
                        "briefTitle": "Test Melanoma Trial",
                    },
                    "conditionsModule": {"conditions": ["Melanoma"]},
                    "designModule": {"phases": ["PHASE2"]},
                    "eligibilityModule": {
                        "eligibilityCriteria": (
                            "Inclusion Criteria:\n"
                            "- Age >= 18 years\n"
                            "- ECOG 0-1\n"
                            "Exclusion Criteria:\n"
                            "- Pregnant\n"
                        )
                    },
                }
            }
        ]
    }


class TestFetchFromClinicalTrials:
    def test_returns_protocol_records(self, mock_ct_response: dict) -> None:
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_ct_response,
                status_code=200,
                raise_for_status=lambda: None,
            )
            records = fetch_from_clinicaltrials("oncology", limit=1)

        assert len(records) == 1
        assert isinstance(records[0], ProtocolRecord)

    def test_extracts_nct_id(self, mock_ct_response: dict) -> None:
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_ct_response,
                status_code=200,
                raise_for_status=lambda: None,
            )
            records = fetch_from_clinicaltrials("oncology", limit=1)

        assert records[0].nct_id == "NCT12345678"

    def test_extracts_eligibility_text(self, mock_ct_response: dict) -> None:
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_ct_response,
                status_code=200,
                raise_for_status=lambda: None,
            )
            records = fetch_from_clinicaltrials("oncology", limit=1)

        assert "Age >= 18" in records[0].document_text
        assert "Pregnant" in records[0].document_text

    def test_handles_empty_response(self) -> None:
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: {"studies": []},
                status_code=200,
                raise_for_status=lambda: None,
            )
            records = fetch_from_clinicaltrials("rare_condition", limit=10)

        assert records == []

    def test_raises_on_invalid_limit(self) -> None:
        with pytest.raises(ValueError, match="limit must be positive"):
            fetch_from_clinicaltrials("oncology", limit=0)


class TestEmitRecords:
    def test_writes_jsonl_file(self, tmp_path: Path) -> None:
        output = tmp_path / "protocols.jsonl"
        records = [
            ProtocolRecord(
                nct_id="NCT1",
                title="Trial 1",
                condition="Cancer",
                phase="Phase 1",
                document_text="Inclusion: Age >= 18",
            )
        ]

        emit_records(records, output_path=output)

        assert output.exists()
        content = output.read_text()
        assert "NCT1" in content
        assert "Trial 1" in content

    def test_writes_multiple_records(self, tmp_path: Path) -> None:
        output = tmp_path / "protocols.jsonl"
        records = [
            ProtocolRecord(
                nct_id=f"NCT{i}",
                title=f"Trial {i}",
                condition="C",
                phase="P",
                document_text="T",
            )
            for i in range(5)
        ]

        emit_records(records, output_path=output)

        lines = output.read_text().strip().split("\n")
        assert len(lines) == 5
