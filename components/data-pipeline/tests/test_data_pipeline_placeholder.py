import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from data_pipeline.download_protocols import (
    ProtocolRecord,
    emit_records,
    fetch_from_clinicaltrials,
    ingest_local_protocols,
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

    def test_raises_on_write_error(self, tmp_path: Path) -> None:
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

        with patch.object(Path, "write_text", side_effect=OSError("nope")):
            with pytest.raises(RuntimeError, match="Failed to write output"):
                emit_records(records, output_path=output)


class TestLocalIngestion:
    def test_ingests_from_manifest(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "protocol.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        manifest_path = tmp_path / "manifest.jsonl"
        manifest_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "source": "clinicaltrials",
                            "url": "https://clinicaltrials.gov/ProvidedDocs/42/NCT12345678/Prot_000.pdf",
                            "path": str(pdf_path),
                            "status": "downloaded",
                        }
                    )
                ]
            )
            + "\n"
        )

        with patch(
            "data_pipeline.download_protocols.extract_text_from_pdf",
            return_value="Sample Protocol\nMore text",
        ):
            records = ingest_local_protocols(manifest_path, limit=5)

        assert len(records) == 1
        assert records[0].title == "Sample Protocol"
        assert records[0].source == "clinicaltrials"
        assert records[0].nct_id == "NCT12345678"
