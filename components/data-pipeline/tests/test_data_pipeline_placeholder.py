import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from data_pipeline.download_protocols import (
    ProtocolRecord,
    _build_record_from_entry,
    _derive_title,
    _extract_registry_id,
    emit_records,
    extract_text_from_pdf,
    fetch_from_clinicaltrials,
    ingest_local_protocols,
    main,
    read_manifest_entries,
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
    def test_handles_pagination(self) -> None:
        page_one = {
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": "NCT11111111",
                            "briefTitle": "Trial One",
                        },
                        "conditionsModule": {"conditions": ["Melanoma"]},
                        "designModule": {"phases": ["PHASE2"]},
                        "eligibilityModule": {"eligibilityCriteria": "Text"},
                    }
                }
            ],
            "nextPageToken": "token-1",
        }
        page_two = {
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": "NCT22222222",
                            "briefTitle": "Trial Two",
                        },
                        "conditionsModule": {"conditions": ["Lung"]},
                        "designModule": {"phases": ["PHASE3"]},
                        "eligibilityModule": {"eligibilityCriteria": "More text"},
                    }
                }
            ]
        }

        with patch("httpx.get") as mock_get:
            captured_params: list[dict[str, str | int]] = []

            def _side_effect(*_args: object, **kwargs: object) -> MagicMock:
                params = kwargs.get("params")
                if isinstance(params, dict):
                    captured_params.append(dict(params))
                response = (
                    page_one if len(captured_params) == 1 else page_two
                )
                return MagicMock(
                    json=lambda: response,
                    status_code=200,
                    raise_for_status=lambda: None,
                )

            mock_get.side_effect = _side_effect
            records = fetch_from_clinicaltrials("oncology", limit=2)

        assert [record.nct_id for record in records] == ["NCT11111111", "NCT22222222"]
        assert "pageToken" not in captured_params[0]
        assert captured_params[1]["pageToken"] == "token-1"

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
    def test_writes_to_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        records = [
            ProtocolRecord(
                nct_id="NCT1",
                title="Trial 1",
                condition="Cancer",
                phase="Phase 1",
                document_text="Inclusion: Age >= 18",
            ),
            ProtocolRecord(
                nct_id="NCT2",
                title="Trial 2",
                condition="Cancer",
                phase="Phase 2",
                document_text="Inclusion: Age >= 18",
            ),
        ]

        emit_records(records, output_path=None)

        captured = capsys.readouterr().out.strip().splitlines()
        assert len(captured) == 2
        assert "NCT1" in captured[0]
        assert "NCT2" in captured[1]

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


class TestPdfExtraction:
    def test_extract_text_from_pdf(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "protocol.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        page_with_text = MagicMock()
        page_with_text.extract_text.return_value = "Page one"
        page_without_text = MagicMock()
        page_without_text.extract_text.return_value = None
        page_two = MagicMock()
        page_two.extract_text.return_value = "Page two"

        with patch("data_pipeline.download_protocols.PdfReader") as mock_reader:
            mock_reader.return_value.pages = [
                page_with_text,
                page_without_text,
                page_two,
            ]
            content = extract_text_from_pdf(pdf_path)

        assert content == "Page one\nPage two"


class TestTitleAndRegistryHelpers:
    def test_derive_title_prefers_first_line(self, tmp_path: Path) -> None:
        path = tmp_path / "protocol_file.pdf"
        title = _derive_title(path, "Trial Title\nMore text")
        assert title == "Trial Title"

    def test_derive_title_falls_back_to_filename(self, tmp_path: Path) -> None:
        path = tmp_path / "trial_protocol-file.pdf"
        title = _derive_title(path, " \n")
        assert title == "trial protocol file"

    def test_extract_registry_id_nct(self) -> None:
        registry_id, registry_type = _extract_registry_id(
            "https://clinicaltrials.gov/study/NCT12345678"
        )
        assert registry_id == "NCT12345678"
        assert registry_type == "nct"

    def test_extract_registry_id_isrctn(self) -> None:
        registry_id, registry_type = _extract_registry_id(
            "https://www.isrctn.com/ISRCTN12345678"
        )
        assert registry_id == "ISRCTN12345678"
        assert registry_type == "isrctn"

    def test_extract_registry_id_missing(self) -> None:
        registry_id, registry_type = _extract_registry_id("https://example.com")
        assert registry_id is None
        assert registry_type is None


class TestManifestParsing:
    def test_read_manifest_entries_skips_invalid_lines(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "manifest.jsonl"
        manifest_path.write_text(
            "\n".join(
                [
                    json.dumps({"status": "downloaded", "path": "file.pdf"}),
                    '{"bad": "json"',
                    json.dumps(["not-a-dict"]),
                    "",
                ]
            )
        )

        entries = read_manifest_entries(manifest_path)

        assert entries == [{"status": "downloaded", "path": "file.pdf"}]


class TestBuildRecordFromEntry:
    def test_skips_non_downloaded_entries(self) -> None:
        entry = {"status": "failed"}
        assert _build_record_from_entry(entry) is None

    def test_skips_missing_path(self) -> None:
        entry = {"status": "downloaded"}
        assert _build_record_from_entry(entry) is None

    def test_skips_missing_file(self, tmp_path: Path) -> None:
        entry = {"status": "downloaded", "path": str(tmp_path / "missing.pdf")}
        assert _build_record_from_entry(entry) is None

    def test_skips_pdf_parse_error(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "protocol.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        entry = {"status": "downloaded", "path": str(pdf_path)}
        with patch(
            "data_pipeline.download_protocols.extract_text_from_pdf",
            side_effect=Exception("boom"),
        ):
            assert _build_record_from_entry(entry) is None

    def test_skips_empty_text(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "protocol.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        entry = {"status": "downloaded", "path": str(pdf_path)}
        with patch(
            "data_pipeline.download_protocols.extract_text_from_pdf",
            return_value="",
        ):
            assert _build_record_from_entry(entry) is None

    def test_builds_record_with_derived_registry(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "protocol.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        entry = {
            "status": "downloaded",
            "path": str(pdf_path),
            "url": "https://clinicaltrials.gov/study/NCT12345678",
            "source": "clinicaltrials",
        }
        with patch(
            "data_pipeline.download_protocols.extract_text_from_pdf",
            return_value="Sample Protocol\nMore text",
        ):
            record = _build_record_from_entry(entry)

        assert record is not None
        assert record.nct_id == "NCT12345678"
        assert record.registry_id == "NCT12345678"
        assert record.registry_type == "nct"
        assert record.title == "Sample Protocol"
        assert record.source == "clinicaltrials"


class TestCliEntrypoint:
    def test_main_local_path(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "manifest.jsonl"
        manifest_path.write_text("")
        with (
            patch(
                "data_pipeline.download_protocols.ingest_local_protocols"
            ) as mock_ingest,
            patch("data_pipeline.download_protocols.emit_records") as mock_emit,
            patch(
                "sys.argv",
                ["prog", "--local", "--manifest-path", str(manifest_path)],
            ),
        ):
            mock_ingest.return_value = []
            main()

        mock_ingest.assert_called_once_with(manifest_path, 50)
        mock_emit.assert_called_once_with([], None)

    def test_main_remote_path(self) -> None:
        with (
            patch(
                "data_pipeline.download_protocols.fetch_from_clinicaltrials"
            ) as mock_fetch,
            patch("data_pipeline.download_protocols.emit_records") as mock_emit,
            patch("sys.argv", ["prog", "--query", "breast", "--limit", "3"]),
        ):
            mock_fetch.return_value = []
            main()

        mock_fetch.assert_called_once_with("breast", 3)
        mock_emit.assert_called_once_with([], None)
