from unittest.mock import AsyncMock

import pytest

from extraction_service.chunking import Paragraph
from extraction_service.pipeline import (
    ExtractionConfig,
    ExtractionPipeline,
    iter_normalized_texts,
    normalize_criterion_text,
)
from extraction_service.schemas import ExtractedCriterion, ExtractionResult


def test_normalize_criterion_text_collapses_whitespace() -> None:
    text = "  Age   >=   18 years.  "
    assert normalize_criterion_text(text) == "Age >= 18 years"


def test_iter_normalized_texts_yields_normalized_items() -> None:
    raw = ["  A  .", "B", "  C   "]
    assert list(iter_normalized_texts(raw)) == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_extract_from_paragraphs_parallel_handles_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_invoke(_vars: object) -> ExtractionResult:
        return ExtractionResult(criteria=[])

    monkeypatch.setattr(
        "extraction_service.pipeline.create_react_agent",
        lambda **_kwargs: _noop_invoke,
    )
    monkeypatch.setattr(
        "extraction_service.pipeline.create_structured_extractor",
        lambda **_kwargs: _noop_invoke,
    )

    pipeline = ExtractionPipeline(
        config=ExtractionConfig(max_concurrency=2),
    )

    paragraphs = [
        Paragraph(text="a", page_number=1, paragraph_index=0),
        Paragraph(text="b", page_number=1, paragraph_index=1),
        Paragraph(text="c", page_number=1, paragraph_index=2),
    ]

    async def _fake_extract(
        paragraph: Paragraph, *_args: object
    ) -> list[ExtractedCriterion]:
        if paragraph.text == "b":
            raise ValueError("boom")
        if paragraph.text == "c":
            return []
        return [
            ExtractedCriterion(
                text="Age >= 18",
                criterion_type="inclusion",
                confidence=0.9,
            )
        ]

    pipeline._extract_from_paragraph = AsyncMock(side_effect=_fake_extract)

    results = await pipeline._extract_from_paragraphs(paragraphs)
    assert len(results) == 1
    assert results[0].text == "Age >= 18"
