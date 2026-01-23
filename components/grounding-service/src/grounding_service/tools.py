"""LangChain tools for grounding service.

This module provides tools that wrap MedGemma for medical interpretation
and can be used by the Gemini orchestrator agent.
"""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

try:
    from langchain_core.tools import tool  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    # Minimal fallback so this module can be imported without LangChain installed.
    def _tool(func=None, **_kwargs):  # type: ignore[no-redef]
        if func is None:
            return lambda f: f
        return func

    tool = _tool  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Initialize Jinja2 environment for prompt templates
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_JINJA_ENV = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)))


@tool
def interpret_medical_text(text: str, context: str = "criterion") -> str:
    """Use MedGemma to interpret medical text and identify clinical concepts.

    Args:
        text: The medical text to interpret (criterion, diagnosis, etc.)
        context: Type of text - 'criterion', 'diagnosis', 'lab', 'medication'

    Returns:
        JSON with identified medical concepts, their clinical significance,
        and suggested UMLS search terms.
    """
    from inference import AgentConfig, create_model_loader

    cfg = AgentConfig.from_env()  # Uses VERTEX_ENDPOINT_ID for MedGemma
    model = create_model_loader(cfg)()

    # Load and render prompt template
    template = _JINJA_ENV.get_template("interpret_medical_text.j2")
    prompt = template.render(context=context, text=text)

    try:
        result = model.invoke([("user", prompt)])
        return result.content
    except Exception as e:
        logger.error("Error in interpret_medical_text: %s", e, exc_info=True)
        error_response = (
            f'{{"error": "MedGemma interpretation failed: {str(e)}", '
            '"concepts": [], "thresholds": [], "interpretation": ""}'
        )
        return error_response
