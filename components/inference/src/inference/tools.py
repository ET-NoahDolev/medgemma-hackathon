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


@tool
def extract_field_mapping(criterion_text: str) -> str:
    """Extract structured field mapping from a single criterion.

    Args:
        criterion_text: A single criterion sentence (1-3 sentences max).
            Example: "Age >= 18 years"

    Returns:
        Raw text response from the model.
    """
    from inference import AgentConfig, create_model_loader

    cfg = AgentConfig.from_env()
    model = create_model_loader(cfg)()

    prompt = f"""Extract the field mapping from this criterion.

Criterion: {criterion_text}

Return the field mapping details clearly in plain text."""

    try:
        result = model.invoke([("user", prompt)])
        return _coerce_model_output(result)
    except Exception as exc:
        logger.error("Error in extract_field_mapping: %s", exc, exc_info=True)
        raise


@tool
def classify_criterion(criterion_text: str) -> str:
    """Classify a criterion as inclusion or exclusion.

    Args:
        criterion_text: A single criterion sentence.

    Returns:
        Raw text response from the model.
    """
    from inference import AgentConfig, create_model_loader

    cfg = AgentConfig.from_env()
    model = create_model_loader(cfg)()

    prompt = f"""Classify this criterion as inclusion or exclusion.

Criterion: {criterion_text}

Provide the label and reasoning in plain text."""

    try:
        result = model.invoke([("user", prompt)])
        return _coerce_model_output(result)
    except Exception as exc:
        logger.error("Error in classify_criterion: %s", exc, exc_info=True)
        raise


@tool
def identify_medical_concepts(text: str) -> str:
    """Identify medical concepts in text for UMLS grounding.

    Args:
        text: Short medical text (1-3 sentences).

    Returns:
        Raw text response from the model.
    """
    from inference import AgentConfig, create_model_loader

    cfg = AgentConfig.from_env()
    model = create_model_loader(cfg)()

    prompt = (
        "Identify medical concepts in this text that should be grounded to "
        "UMLS/SNOMED.\n\n"
        f"Text: {text}\n\n"
        "Provide the concepts and a brief interpretation in plain text."
    )

    try:
        result = model.invoke([("user", prompt)])
        return _coerce_model_output(result)
    except Exception as exc:
        logger.error("Error in identify_medical_concepts: %s", exc, exc_info=True)
        raise
