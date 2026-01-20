from pathlib import Path
from unittest.mock import MagicMock, patch

from data_pipeline.download_protocols import ProtocolRecord
from data_pipeline.loader import bulk_load_protocols, load_single_protocol


def test_load_single_protocol_posts_and_extracts(tmp_path: Path) -> None:
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    with patch("data_pipeline.loader.extract_text_from_pdf") as mock_extract:
        mock_extract.return_value = "Protocol text"
        with patch("data_pipeline.loader.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"protocol_id": "proto-1"},
                raise_for_status=lambda: None,
            )

            protocol_id = load_single_protocol(pdf, "http://localhost:8000")

    assert protocol_id == "proto-1"
    assert mock_post.call_count == 2


def test_bulk_load_protocols_posts_records(tmp_path: Path) -> None:
    record = ProtocolRecord(
        nct_id="NCT12345678",
        title="Trial 1",
        condition="Cancer",
        phase="Phase 1",
        document_text="Inclusion: Age >= 18",
    )
    record_two = ProtocolRecord(
        nct_id="NCT99999999",
        title="Trial 2",
        condition="Melanoma",
        phase="Phase 2",
        document_text="Exclusion: Pregnant",
    )

    with patch("data_pipeline.loader.ingest_local_protocols") as mock_ingest:
        mock_ingest.return_value = [record, record_two]
        with patch("data_pipeline.loader.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"protocol_id": "proto-1"},
            )

            protocol_ids = bulk_load_protocols(
                manifest_path=tmp_path / "manifest.jsonl",
                api_url="http://localhost:8000",
                limit=2,
            )

    assert protocol_ids == ["proto-1", "proto-1"]
    assert mock_post.call_count == 2
