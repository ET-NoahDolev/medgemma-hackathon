"""Hierarchical extraction pipeline for eligibility criteria."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Iterable, Iterator, Sequence

import anyio
from inference.agent_factory import create_react_agent
from inference.model_factory import create_gemini_model_loader
from shared.mlflow_utils import set_trace_metadata

from extraction_service.chunking import (
    Page,
    Paragraph,
    split_into_pages,
    split_into_paragraphs,
)
from extraction_service.schemas import (
    ExtractedCriterion,
    ExtractionResult,
    PageFilterResult,
    ParagraphFilterResult,
)
from extraction_service.tools import clarify_ambiguity, extract_triplet

logger = logging.getLogger(__name__)

_PIPELINE: "ExtractionPipeline | None" = None


@dataclass(frozen=True)
class ExtractionConfig:
    """Configuration for the extraction pipeline."""

    gemini_model_name: str | None = None
    gcp_project_id: str | None = None
    gcp_region: str = "europe-west4"
    max_page_chars: int = 4000
    max_pages_per_batch: int = 6
    max_paragraphs_per_batch: int = 10

    @classmethod
    def from_env(cls) -> "ExtractionConfig":
        """Create config from environment variables."""
        return cls(
            gemini_model_name=os.getenv("GEMINI_MODEL_NAME"),
            gcp_project_id=os.getenv("GCP_PROJECT_ID"),
            gcp_region=os.getenv("GCP_REGION", "europe-west4"),
            max_page_chars=_read_int_env("EXTRACTION_MAX_PAGE_CHARS", 4000),
            max_pages_per_batch=_read_int_env("EXTRACTION_MAX_PAGES_PER_BATCH", 6),
            max_paragraphs_per_batch=_read_int_env(
                "EXTRACTION_MAX_PARAGRAPHS_PER_BATCH", 10
            ),
        )


class ExtractionPipeline:
    """Hierarchical extraction pipeline."""

    def __init__(self, *, config: ExtractionConfig | None = None) -> None:
        """Initialize pipeline with Gemini configuration."""
        self.config = config or ExtractionConfig.from_env()
        self._model_loader = create_gemini_model_loader(
            model_name=self.config.gemini_model_name,
            project=self.config.gcp_project_id,
            region=self.config.gcp_region,
        )
        self._prompts_dir = Path(__file__).parent / "prompts"
        self._page_filter_agent = create_react_agent(
            model_loader=self._model_loader,
            prompts_dir=self._prompts_dir,
            tools=[],
            response_schema=PageFilterResult,
            system_template="system.j2",
            user_template="filter_pages.j2",
        )
        self._paragraph_filter_agent = create_react_agent(
            model_loader=self._model_loader,
            prompts_dir=self._prompts_dir,
            tools=[],
            response_schema=ParagraphFilterResult,
            system_template="system.j2",
            user_template="filter_paragraphs.j2",
        )
        self._extract_agent = create_react_agent(
            model_loader=self._model_loader,
            prompts_dir=self._prompts_dir,
            tools=[extract_triplet, clarify_ambiguity],
            response_schema=ExtractionResult,
            system_template="system.j2",
            user_template="extract_criteria.j2",
        )

    async def extract_criteria_async(
        self,
        document_text: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> list[ExtractedCriterion]:
        """Extract criteria using hierarchical filtering.

        Args:
            document_text: Document text to extract from.
            session_id: Optional session ID for trace grouping.
            user_id: Optional user ID for trace grouping.
        """
        pages = split_into_pages(document_text, max_chars=self.config.max_page_chars)
        if not pages:
            return []

        relevant_pages = await self._filter_pages(pages, session_id, user_id)
        relevant_paragraphs = await self._filter_paragraphs(
            relevant_pages, session_id, user_id
        )
        criteria = await self._extract_from_paragraphs(
            relevant_paragraphs, session_id, user_id
        )
        return _deduplicate(criteria)

    async def extract_criteria_stream_async(
        self, document_text: str
    ) -> AsyncIterator[ExtractedCriterion]:
        """Stream criteria extraction results."""
        pages = split_into_pages(document_text, max_chars=self.config.max_page_chars)
        if not pages:
            return

        relevant_pages = await self._filter_pages(pages)
        relevant_paragraphs = await self._filter_paragraphs(relevant_pages)
        seen: set[str] = set()
        for paragraph in relevant_paragraphs:
            extracted = await self._extract_from_paragraph(paragraph)
            for item in extracted:
                normalized = normalize_criterion_text(item.text)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                yield item

    async def _filter_pages(
        self, pages: Sequence[Page], session_id: str | None = None, user_id: str | None = None
    ) -> list[Page]:
        if not pages:
            return []

        # Set trace metadata before agent invocation
        set_trace_metadata(user_id=user_id, session_id=session_id)

        selected_numbers: set[int] = set()
        for batch in _chunked(pages, self.config.max_pages_per_batch):
            result = await self._page_filter_agent({"pages": batch})
            selected_numbers.update(result.pages)

        return [page for page in pages if page.page_number in selected_numbers]

    async def _filter_paragraphs(
        self, pages: Sequence[Page], session_id: str | None = None, user_id: str | None = None
    ) -> list[Paragraph]:
        # Set trace metadata before agent invocation
        set_trace_metadata(user_id=user_id, session_id=session_id)

        relevant: list[Paragraph] = []
        for page in pages:
            paragraphs = split_into_paragraphs(page)
            if not paragraphs:
                continue
            for batch in _chunked(paragraphs, self.config.max_paragraphs_per_batch):
                result = await self._paragraph_filter_agent(
                    {"page_number": page.page_number, "paragraphs": batch}
                )
                relevant.extend(
                    paragraph
                    for paragraph in batch
                    if paragraph.paragraph_index in result.paragraph_indices
                )
        return relevant

    async def _extract_from_paragraphs(
        self,
        paragraphs: Sequence[Paragraph],
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> list[ExtractedCriterion]:
        criteria: list[ExtractedCriterion] = []
        for paragraph in paragraphs:
            criteria.extend(
                await self._extract_from_paragraph(paragraph, session_id, user_id)
            )
        return criteria

    async def _extract_from_paragraph(
        self,
        paragraph: Paragraph,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> list[ExtractedCriterion]:
        # Set trace metadata before agent invocation
        set_trace_metadata(user_id=user_id, session_id=session_id)
        result = await self._extract_agent({"paragraph": paragraph})
        return result.criteria


def extract_criteria(document_text: str) -> list[ExtractedCriterion]:
    """Synchronous wrapper for extracting criteria."""
    pipeline = _get_pipeline()
    return anyio.run(pipeline.extract_criteria_async, document_text)


def extract_criteria_stream(document_text: str) -> Iterator[ExtractedCriterion]:
    """Synchronous streaming wrapper for criteria extraction."""
    pipeline = _get_pipeline()
    items = anyio.run(_collect_stream, pipeline, document_text)
    yield from items


async def extract_criteria_async(
    document_text: str,
    session_id: str | None = None,
    user_id: str | None = None,
) -> list[ExtractedCriterion]:
    """Async wrapper for extracting criteria.

    Args:
        document_text: Document text to extract from.
        session_id: Optional session ID for trace grouping.
        user_id: Optional user ID for trace grouping.
    """
    pipeline = _get_pipeline()
    return await pipeline.extract_criteria_async(document_text, session_id, user_id)


def iter_normalized_texts(items: Iterable[str]) -> Iterator[str]:
    """Yield normalized criterion text items."""
    for item in items:
        normalized = normalize_criterion_text(item)
        if normalized:
            yield normalized


def normalize_criterion_text(text: str) -> str:
    """Normalize criterion text for deduplication."""
    cleaned = " ".join(text.split())
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)
    return cleaned.rstrip(".;:").strip()


def _get_pipeline() -> ExtractionPipeline:
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = ExtractionPipeline()
    return _PIPELINE


def _chunked(items: Sequence[Page] | Sequence[Paragraph], size: int) -> Iterator[list]:
    if size <= 0:
        raise ValueError("Chunk size must be positive.")
    for idx in range(0, len(items), size):
        yield list(items[idx : idx + size])


def _deduplicate(
    criteria: Sequence[ExtractedCriterion],
) -> list[ExtractedCriterion]:
    deduped: list[ExtractedCriterion] = []
    seen: set[str] = set()
    for item in criteria:
        normalized = normalize_criterion_text(item.text)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(item)
    return deduped


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid integer for {name}: {raw}") from exc


async def _collect_stream(
    pipeline: ExtractionPipeline, document_text: str
) -> list[ExtractedCriterion]:
    items: list[ExtractedCriterion] = []
    async for item in pipeline.extract_criteria_stream_async(document_text):
        items.append(item)
    return items
