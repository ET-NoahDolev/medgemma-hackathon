"""LangChain tools for MedGemma-based extraction.

This module provides focused tools that use MedGemma for specific extraction tasks
with structured Pydantic outputs.
"""

from __future__ import annotations

import logging

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

    prompt = (
        "Identify medical concepts in this text that should be grounded to "
        "UMLS/SNOMED.\n\n"
        f"Text: {text}\n\n"
        f"{format_instructions}"
    )

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
        return result_json
    except Exception as e:
        logger.error("Error in identify_medical_concepts: %s", e, exc_info=True)
        error_response = (
            f'{{"error": "MedGemma concept identification failed: {str(e)}", '
            '"concepts": [], "interpretation": ""}'
        )
        return error_response
