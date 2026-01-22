"""LangChain tools for MedGemma-based extraction.

This module provides focused tools that use MedGemma for specific extraction tasks
with structured Pydantic outputs.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    from langchain_core.output_parsers import PydanticOutputParser
    from langchain_core.tools import tool
except ImportError:  # pragma: no cover
    # Minimal fallback so this module can be imported without LangChain installed.
    def _tool(func=None, **_kwargs):  # type: ignore[no-redef]
        if func is None:
            return lambda f: f
        return func

    tool = _tool  # type: ignore[assignment]
    PydanticOutputParser = None  # type: ignore[assignment, misc]

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
def extract_field_mapping(criterion_text: str) -> str:
    """Extract structured field mapping from a single criterion.

    Args:
        criterion_text: A single criterion sentence (1-3 sentences max).
            Example: "Age >= 18 years"

    Returns:
        JSON string with field_name, relation_type, value, unit, confidence.
        If no field mapping found, returns null values.
    """
    from inference import AgentConfig, create_model_loader
    from inference.schemas import FieldMappingResult

    if PydanticOutputParser is None:
        logger.error("PydanticOutputParser not available")
        return '{"error": "PydanticOutputParser not available"}'

    cfg = AgentConfig.from_env()
    model = create_model_loader(cfg)()

    # Use PydanticOutputParser to ensure structured output
    parser = PydanticOutputParser(pydantic_object=FieldMappingResult)
    format_instructions = parser.get_format_instructions()

    prompt = f"""Extract the field mapping from this criterion.

Criterion: {criterion_text}

{format_instructions}

Return the structured output matching the schema above."""

    try:
        # Use with_structured_output if available, otherwise use parser
        try:
            structured_model = model.with_structured_output(FieldMappingResult)
            result = structured_model.invoke([("user", prompt)])
            result_json = result.model_dump_json()
        except (AttributeError, TypeError):
            # Fallback: use parser
            result = model.invoke([("user", prompt)])
            parsed = parser.parse(result.content)
            result_json = parsed.model_dump_json()

        # MLflow logging
        if MLFLOW_AVAILABLE and mlflow is not None:
            with mlflow.start_run(run_name="medgemma_extract_field", nested=True):
                mlflow.log_param("input_length", len(criterion_text))
                mlflow.log_text(criterion_text, "input.txt")
                mlflow.log_text(result_json, "output.json")

                # Parse and log structured fields for easier querying
                try:
                    parsed = FieldMappingResult.model_validate_json(result_json)
                    mlflow.log_params(
                        {
                            "field_name": parsed.field_name or "null",
                            "relation_type": parsed.relation_type or "null",
                            "confidence": parsed.confidence,
                        }
                    )
                except Exception as e:
                    mlflow.log_param("parse_error", str(e))
                    mlflow.log_param("output_incomplete", True)

        return result_json
    except Exception as e:
        logger.error("Error in extract_field_mapping: %s", e, exc_info=True)
        error_response = (
            f'{{"error": "MedGemma extraction failed: {str(e)}", '
            '"field_name": null, "relation_type": null, '
            '"value": null, "unit": null, "confidence": 0.0}'
        )
        return error_response


@tool
def classify_criterion(criterion_text: str) -> str:
    """Classify a criterion as inclusion or exclusion.

    Args:
        criterion_text: A single criterion sentence.

    Returns:
        JSON string with criterion_type, confidence, reasoning.
    """
    from inference import AgentConfig, create_model_loader
    from inference.schemas import CriterionClassificationResult

    if PydanticOutputParser is None:
        logger.error("PydanticOutputParser not available")
        return '{"error": "PydanticOutputParser not available"}'

    cfg = AgentConfig.from_env()
    model = create_model_loader(cfg)()

    parser = PydanticOutputParser(pydantic_object=CriterionClassificationResult)
    format_instructions = parser.get_format_instructions()

    prompt = f"""Classify this criterion as inclusion or exclusion.

Criterion: {criterion_text}

{format_instructions}"""

    try:
        try:
            structured_model = model.with_structured_output(
                CriterionClassificationResult
            )
            result = structured_model.invoke([("user", prompt)])
            result_json = result.model_dump_json()
        except (AttributeError, TypeError):
            result = model.invoke([("user", prompt)])
            parsed = parser.parse(result.content)
            result_json = parsed.model_dump_json()

        # MLflow logging
        if MLFLOW_AVAILABLE and mlflow is not None:
            with mlflow.start_run(
                run_name="medgemma_classify_criterion", nested=True
            ):
                mlflow.log_param("input_length", len(criterion_text))
                mlflow.log_text(criterion_text, "input.txt")
                mlflow.log_text(result_json, "output.json")

                try:
                    parsed = CriterionClassificationResult.model_validate_json(
                        result_json
                    )
                    mlflow.log_params(
                        {
                            "criterion_type": parsed.criterion_type,
                            "confidence": parsed.confidence,
                        }
                    )
                except Exception as e:
                    mlflow.log_param("parse_error", str(e))
                    mlflow.log_param("output_incomplete", True)

        return result_json
    except Exception as e:
        logger.error("Error in classify_criterion: %s", e, exc_info=True)
        error_response = (
            f'{{"error": "MedGemma classification failed: {str(e)}", '
            '"criterion_type": "inclusion", "confidence": 0.0, '
            '"reasoning": "Error occurred during classification"}'
        )
        return error_response


@tool
def identify_medical_concepts(text: str) -> str:
    """Identify medical concepts in text for UMLS grounding.

    Args:
        text: Short medical text (1-3 sentences).

    Returns:
        JSON string with concepts list and interpretation.
    """
    from inference import AgentConfig, create_model_loader
    from inference.schemas import MedicalConceptsResult

    if PydanticOutputParser is None:
        logger.error("PydanticOutputParser not available")
        return '{"error": "PydanticOutputParser not available"}'

    cfg = AgentConfig.from_env()
    model = create_model_loader(cfg)()

    parser = PydanticOutputParser(pydantic_object=MedicalConceptsResult)
    format_instructions = parser.get_format_instructions()

    prompt = f"""Identify medical concepts in this text that should be grounded to UMLS/SNOMED.

Text: {text}

{format_instructions}"""

    try:
        try:
            structured_model = model.with_structured_output(MedicalConceptsResult)
            result = structured_model.invoke([("user", prompt)])
            result_json = result.model_dump_json()
        except (AttributeError, TypeError):
            result = model.invoke([("user", prompt)])
            parsed = parser.parse(result.content)
            result_json = parsed.model_dump_json()

        # MLflow logging
        if MLFLOW_AVAILABLE and mlflow is not None:
            with mlflow.start_run(
                run_name="medgemma_identify_concepts", nested=True
            ):
                mlflow.log_param("input_length", len(text))
                mlflow.log_text(text, "input.txt")
                mlflow.log_text(result_json, "output.json")

                try:
                    parsed = MedicalConceptsResult.model_validate_json(result_json)
                    mlflow.log_param("concepts_count", len(parsed.concepts))
                except Exception as e:
                    mlflow.log_param("parse_error", str(e))
                    mlflow.log_param("output_incomplete", True)

        return result_json
    except Exception as e:
        logger.error("Error in identify_medical_concepts: %s", e, exc_info=True)
        error_response = (
            f'{{"error": "MedGemma concept identification failed: {str(e)}", '
            '"concepts": [], "interpretation": ""}'
        )
        return error_response
