from __future__ import annotations

from dataclasses import dataclass

import pytest

from api_service.ingestion import ingest_protocol_document_text
from api_service.storage import Storage, get_engine


@dataclass
class FakeGroundingCandidate:
    code: str
    display: str
    ontology: str
    confidence: float


@dataclass
class FakeFieldMapping:
    field: str
    relation: str
    value: str
    confidence: float


@pytest.mark.asyncio
async def test_ingestion_pipeline_stores_triplet_and_grounding(
    monkeypatch: pytest.MonkeyPatch,
    fake_services,
) -> None:
    storage = Storage(get_engine())

    def _extract_criteria_stream(_text: str):
        yield from fake_services.extracted

    async def _extract_criteria_async(_text: str):
        return fake_services.extracted

    class FakeUmlsClient:
        def __init__(self, *args, **kwargs) -> None:
            _ = args
            _ = kwargs

        def __enter__(self) -> "FakeUmlsClient":
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def search_snomed(self, _text: str):
            return [
                FakeGroundingCandidate(
                    code="371273006",
                    display="Age (finding)",
                    ontology="SNOMEDCT_US",
                    confidence=0.88,
                )
            ]

    def _propose_field_mapping(_text: str):
        return [
            FakeFieldMapping(
                field="demographics.age",
                relation=">=",
                value="18",
                confidence=0.77,
            )
        ]

    monkeypatch.setattr(
        "api_service.ingestion.extraction_pipeline.extract_criteria_stream",
        _extract_criteria_stream,
    )
    monkeypatch.setattr(
        "api_service.ingestion.extraction_pipeline.extract_criteria_async",
        _extract_criteria_async,
    )
    monkeypatch.setattr("api_service.ingestion.umls_client.UmlsClient", FakeUmlsClient)
    monkeypatch.setattr(
        "api_service.ingestion.umls_client.propose_field_mapping",
        _propose_field_mapping,
    )
    monkeypatch.setattr(
        "api_service.ingestion.extract_triplet",
        lambda _text: '{"entity":"age","relation":">=","value":"18","unit":"years"}',
    )

    stored = await ingest_protocol_document_text(
        protocol_id="proto-1",
        document_text="Inclusion: Age >= 18 years.",
        storage=storage,
        umls_api_key="test-key",
    )

    assert len(stored) == 1
    criterion = stored[0]
    assert criterion.entity == "age"
    assert criterion.relation == ">="
    assert criterion.value == "18"
    assert criterion.unit == "years"
    assert criterion.snomed_codes == ["371273006"]
