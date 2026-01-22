"""LangChain tools for grounding service.

This module provides tools that wrap MedGemma for medical interpretation
and can be used by the Gemini orchestrator agent.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    from langchain_core.tools import tool  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    # Minimal fallback so this module can be imported without LangChain installed.
    def _tool(func=None, **_kwargs):  # type: ignore[no-redef]
        if func is None:
            return lambda f: f
        return func

    tool = _tool  # type: ignore[assignment]

# Try to import mlflow (optional dependency for dev/observability)
mlflow: Any | None
try:
    import mlflow as _mlflow

    MLFLOW_AVAILABLE = True
    mlflow = _mlflow
except ImportError:
    mlflow = None
    MLFLOW_AVAILABLE = False

logger = logging.getLogger(__name__)


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

    prompt = f"""Analyze this {context} and identify:
1. Medical concepts that should be grounded to UMLS/SNOMED
2. Numeric thresholds (e.g., age >= 18, HbA1c < 7.0)
3. Clinical significance

Text: {text}

Return JSON with: concepts (list of terms to search),
thresholds (field/operator/value), interpretation (brief clinical meaning)"""

    try:
        # MLflow logging for tool invocation
        if MLFLOW_AVAILABLE and mlflow is not None:
            with mlflow.start_run(run_name="medgemma_interpret", nested=True):
                mlflow.log_param("context", context)
                mlflow.log_param("input_length", len(text))
                mlflow.log_text(text, "input_text.txt")

                result = model.invoke([("user", prompt)])

                mlflow.log_text(result.content, "interpretation.json")
                return result.content
        else:
            result = model.invoke([("user", prompt)])
            return result.content
    except Exception as e:
        logger.error("Error in interpret_medical_text: %s", e, exc_info=True)
        error_response = (
            f'{{"error": "MedGemma interpretation failed: {str(e)}", '
            '"concepts": [], "thresholds": [], "interpretation": ""}'
        )
        return error_response
