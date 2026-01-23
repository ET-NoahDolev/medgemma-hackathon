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
    """Normalize model output to text for tool responses."""
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(result, str):
        return result
    return str(result)


