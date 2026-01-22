"""LangChain tools for iterative criteria extraction.

This module provides tools that enable the ReAct agent to extract criteria
in batches, overcoming token limits by allowing multiple iterations.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


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

    def create_tools(self) -> list[Any]:
        """Create LangChain tools bound to this factory's accumulator.

        Returns:
            List of tool functions for use with create_react_agent.
        """
        try:
            from langchain_core.tools import tool
        except ImportError:
            logger.warning("langchain_core not available; returning empty tools list")
            return []

        @tool
        def submit_criteria(criteria: list[dict[str, Any]]) -> str:
            """Submit a batch of extracted criteria.

            Call this tool as you find criteria in the document. You can call it
            multiple times to submit criteria in batches.

            Args:
                criteria: List of criteria dicts, each with:
                    - text (str): The atomic criterion text
                    - criterion_type (str): Either "inclusion" or "exclusion"
                    - confidence (float, optional): Confidence score 0.0-1.0

            Returns:
                Confirmation message with count of criteria submitted.
            """
            if not isinstance(criteria, list):
                return "Error: criteria must be a list of dictionaries"

            valid_count = 0
            for item in criteria:
                if not isinstance(item, dict):
                    continue
                if "text" not in item or "criterion_type" not in item:
                    continue
                # Normalize criterion_type
                ctype = str(item.get("criterion_type", "")).lower()
                if ctype not in ("inclusion", "exclusion"):
                    ctype = "inclusion"
                normalized = {
                    "text": str(item["text"]).strip(),
                    "criterion_type": ctype,
                    "confidence": float(item.get("confidence", 0.8)),
                }
                if normalized["text"]:
                    self._accumulated.append(normalized)
                    valid_count += 1

            self._submission_count += 1
            total = len(self._accumulated)
            return (
                f"Submitted {valid_count} criteria (batch #{self._submission_count}). "
                f"Total criteria so far: {total}. "
                "Continue extracting or finish if done."
            )

        @tool
        def finish_extraction() -> str:
            """Signal that extraction is complete.

            Call this tool when you have extracted all criteria from the document.

            Returns:
                Summary of extraction results.
            """
            total = len(self._accumulated)
            inc_count = sum(
                1 for c in self._accumulated if c["criterion_type"] == "inclusion"
            )
            exc_count = total - inc_count
            return (
                f"Extraction complete. Total: {total} criteria "
                f"({inc_count} inclusion, {exc_count} exclusion)."
            )

        return [submit_criteria, finish_extraction]

    def get_results(self) -> list[dict[str, Any]]:
        """Get all accumulated criteria.

        Returns:
            List of criterion dicts with text, criterion_type, and confidence.
        """
        return self._accumulated.copy()

    def get_results_as_schema(self) -> list[Any]:
        """Get accumulated criteria as ExtractedCriterion objects.

        Returns:
            List of ExtractedCriterion instances.
        """
        from extraction_service.schemas import ExtractedCriterion

        return [ExtractedCriterion(**c) for c in self._accumulated]

    def clear(self) -> None:
        """Reset the accumulator for a new extraction."""
        self._accumulated.clear()
        self._submission_count = 0

    @property
    def has_results(self) -> bool:
        """Check if any criteria have been accumulated."""
        return len(self._accumulated) > 0
