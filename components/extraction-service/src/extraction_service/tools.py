"""LangChain tools for iterative criteria extraction.

This module provides tools that enable the ReAct agent to extract criteria
in batches, overcoming token limits by allowing multiple iterations.
"""

from __future__ import annotations

import json
import logging
from typing import Any

try:
    from langchain_core.tools import tool
except ImportError:  # pragma: no cover
    # Minimal fallback so this module can be imported without LangChain installed.
    def _tool(func=None, **_kwargs):  # type: ignore[no-redef]
        if func is None:
            return lambda f: f
        return func

    tool = _tool  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _coerce_model_output(result: object) -> str:
    """Normalize model output to text for tool responses."""
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(result, str):
        return result
    return str(result)


def _invoke_medgemma(prompt: str) -> str:
    from inference import AgentConfig, create_model_loader

    cfg = AgentConfig.from_env()
    model = create_model_loader(cfg)()
    try:
        result = model.invoke([("user", prompt)])
        return _coerce_model_output(result)
    except Exception as exc:
        logger.error("MedGemma tool invocation failed: %s", exc, exc_info=True)
        raise


@tool
def extract_triplet(text: str) -> str:
    """Extract entity/relation/value triplet from criterion text.

    Args:
        text: Criterion text, e.g., "Age 18 years or older".

    Returns:
        JSON string with entity, relation, value.
    """
    prompt = (
        "Extract a structured entity/relation/value triplet from this criterion.\n"
        "Return a compact JSON object with keys: entity, relation, value.\n\n"
        f"Criterion: {text}\n"
    )
    return _invoke_medgemma(prompt)


@tool
def classify_criterion(text: str, context: str = "") -> str:
    """Classify text as inclusion/exclusion criterion.

    Args:
        text: Candidate criterion text.
        context: Optional surrounding context for disambiguation.

    Returns:
        JSON string with is_criterion, criterion_type, confidence.
    """
    prompt = (
        "Classify whether this text is an inclusion or exclusion criterion.\n"
        "Return JSON with keys: is_criterion (true/false), criterion_type "
        "('inclusion'/'exclusion'), confidence (0-1).\n\n"
        f"Text: {text}\n"
    )
    if context:
        prompt += f"\nContext: {context}\n"
    return _invoke_medgemma(prompt)


@tool
def clarify_ambiguity(question: str, text: str) -> str:
    """Clarify an ambiguous criterion with a targeted question.

    Args:
        question: Clarification question to answer.
        text: The ambiguous text segment.

    Returns:
        Clarification response text.
    """
    prompt = (
        "Answer the clarification question about the criterion.\n\n"
        f"Question: {question}\n"
        f"Text: {text}\n"
    )
    return _invoke_medgemma(prompt)


class ExtractionToolFactory:
    """Factory for creating extraction tools with shared state.

    Each instance maintains its own accumulator for criteria, allowing
    concurrent extractions to operate independently.

    Example:
        factory = ExtractionToolFactory()
        tools = factory.create_tools()
        # ... use tools with agent ...
        criteria = factory.get_results()
    """

    def __init__(self) -> None:
        """Initialize with empty accumulator."""
        self._accumulated: list[dict[str, Any]] = []
        self._submission_count = 0
        self._current_chunk_index: int | None = None
        self._current_chunk_text: str = ""
        self._current_section_type: str | None = None
        self._current_page_hint: int | None = None

    def create_tools(self) -> list[Any]:
        """Create LangChain tools bound to this factory's accumulator."""
        return [
            extract_triplet,
            classify_criterion,
            clarify_ambiguity,
            self._build_submit_criteria_tool(),
            self._build_submit_finding_tool(),
            self._build_finish_tool(),
        ]

    def _build_submit_criteria_tool(self) -> Any:
        @tool
        def submit_criteria(criteria: list[dict[str, Any]]) -> str:
            """Submit a batch of extracted criteria."""
            if not isinstance(criteria, list):
                return "Error: criteria must be a list of dictionaries"

            valid_count = 0
            for item in criteria:
                normalized = self._normalize_criterion_item(item)
                if normalized is None:
                    continue
                self._accumulated.append(normalized)
                valid_count += 1

            self._submission_count += 1
            total = len(self._accumulated)
            return (
                f"Submitted {valid_count} criteria (batch #{self._submission_count}). "
                f"Total criteria so far: {total}. "
                "Continue extracting or finish if done."
            )

        return submit_criteria

    def _normalize_criterion_item(self, item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        if "text" not in item or "criterion_type" not in item:
            return None
        ctype = str(item.get("criterion_type", "")).lower()
        if ctype not in ("inclusion", "exclusion"):
            ctype = "inclusion"
        text = str(item["text"]).strip()
        if not text:
            return None
        return {
            "chunk_index": self._current_chunk_index or 0,
            "has_criteria": True,
            "criterion_type": ctype,
            "text": text,
            "snippet": text,
            "triplet": None,
            "confidence": float(item.get("confidence", 0.8)),
            "source_span": None,
        }

    def _build_submit_finding_tool(self) -> Any:
        @tool
        def submit_finding(finding: dict[str, Any]) -> str:
            """Submit a structured finding for the current chunk."""
            if not isinstance(finding, dict):
                return "Error: finding must be a dictionary"

            normalized = self._normalize_finding_item(finding)
            if normalized is None:
                return "Error: finding.text is required"

            self._accumulated.append(normalized)
            return "Finding recorded."

        return submit_finding

    def _normalize_finding_item(self, finding: dict[str, Any]) -> dict[str, Any] | None:
        text = str(finding.get("text", "")).strip()
        if not text:
            return None
        snippet = str(finding.get("snippet", "")).strip()
        criterion_type = str(finding.get("criterion_type", "")).lower()
        if criterion_type not in ("inclusion", "exclusion"):
            criterion_type = "inclusion"

        triplet = finding.get("triplet")
        if isinstance(triplet, str):
            try:
                triplet = json.loads(triplet)
            except json.JSONDecodeError:
                triplet = None

        source_span = None
        if snippet and self._current_chunk_text:
            start = self._current_chunk_text.find(snippet)
            if start >= 0:
                source_span = (start, start + len(snippet))

        return {
            "chunk_index": self._current_chunk_index or 0,
            "has_criteria": True,
            "criterion_type": criterion_type,
            "text": text,
            "snippet": snippet,
            "triplet": triplet,
            "confidence": float(finding.get("confidence", 0.8)),
            "source_span": source_span,
            "section_type": self._current_section_type,
            "page_hint": self._current_page_hint,
        }

    def _build_finish_tool(self) -> Any:
        @tool
        def finish_extraction() -> str:
            """Signal that extraction is complete."""
            total = len(self._accumulated)
            inc_count = sum(
                1 for c in self._accumulated if c["criterion_type"] == "inclusion"
            )
            exc_count = total - inc_count
            return (
                f"Extraction complete. Total: {total} criteria "
                f"({inc_count} inclusion, {exc_count} exclusion)."
            )

        return finish_extraction

    def get_results(self) -> list[dict[str, Any]]:
        """Get all accumulated criteria.

        Returns:
            List of criterion dicts with text, criterion_type, and confidence.
        """
        return self._accumulated.copy()

    def set_current_chunk(
        self,
        *,
        chunk_index: int,
        chunk_text: str,
        section_type: str | None = None,
        page_hint: int | None = None,
    ) -> None:
        """Update the current chunk metadata for subsequent tool calls."""
        self._current_chunk_index = chunk_index
        self._current_chunk_text = chunk_text
        self._current_section_type = section_type
        self._current_page_hint = page_hint

    def get_chunk_findings(self, chunk_index: int) -> list[dict[str, Any]]:
        """Return findings for a specific chunk index."""
        return [
            item
            for item in self._accumulated
            if item.get("chunk_index") == chunk_index
        ]

    def record_no_criteria(self, chunk_index: int) -> None:
        """Record a placeholder finding when no criteria were found."""
        self._accumulated.append(
            {
                "chunk_index": chunk_index,
                "has_criteria": False,
                "criterion_type": None,
                "text": "",
                "snippet": "",
                "triplet": None,
                "confidence": 0.0,
                "source_span": None,
                "section_type": self._current_section_type,
                "page_hint": self._current_page_hint,
            }
        )

    def clear(self) -> None:
        """Reset the accumulator for a new extraction."""
        self._accumulated.clear()
        self._submission_count = 0
        self._current_chunk_index = None
        self._current_chunk_text = ""

    @property
    def has_results(self) -> bool:
        """Check if any criteria have been accumulated."""
        return len(self._accumulated) > 0
