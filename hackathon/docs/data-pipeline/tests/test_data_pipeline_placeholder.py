import pytest

from data_pipeline import download_protocols


def test_protocol_record_dataclass() -> None:
    record = download_protocols.ProtocolRecord(
        nct_id="NCT00000000",
        title="Example Trial",
        condition="Melanoma",
        phase="Phase 2",
        document_text="Inclusion: Age >= 18.",
    )

    assert record.nct_id == "NCT00000000"
    assert record.title == "Example Trial"
    assert record.condition == "Melanoma"
    assert record.phase == "Phase 2"
    assert record.document_text == "Inclusion: Age >= 18."


def test_download_protocols_returns_list() -> None:
    records = download_protocols.download_protocols(limit=1)

    assert isinstance(records, list)
    assert len(records) == 1
    assert records[0].nct_id == "NCT00000000"


def test_download_protocols_raises_on_invalid_limit() -> None:
    with pytest.raises(ValueError):
        download_protocols.download_protocols(limit=0)


def test_emit_records_returns_none() -> None:
    result = download_protocols.emit_records([])

    assert result is None


def test_main_prints_message(capsys: pytest.CaptureFixture[str]) -> None:
    download_protocols.main()

    captured = capsys.readouterr()
    assert "Download protocols placeholder" in captured.out
