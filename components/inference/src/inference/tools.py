"""LangChain tools for MedGemma-based extraction.

This module provides focused tools that use MedGemma for specific extraction tasks
and return raw text outputs for downstream handling.
"""

from __future__ import annotations

import logging

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
    """Normalize model output to text for tool responses.

    Strips Gemma chat format markers and extracts clean content.
    """
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return _clean_model_output(content)
    if isinstance(result, str):
        return _clean_model_output(result)
    return _clean_model_output(str(result))


def _clean_model_output(text: str) -> str:
    """Strip chat format markers and extract clean JSON/text.

    Handles Gemma-style markers like <end_of_turn>, <start_of_turn>model, etc.
    """
    import re

    # Remove Gemma chat format markers
    text = re.sub(r"<end_of_turn>\s*", "", text)
    text = re.sub(r"<start_of_turn>\s*model\s*", "", text)
    text = re.sub(r"<start_of_turn>\s*user\s*", "", text)
    text = re.sub(r"Output:\s*", "", text)

    # Try to extract JSON from code fence if present
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        return fence_match.group(1).strip()

    return text.strip()


