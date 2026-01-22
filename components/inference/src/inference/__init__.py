"""Shared MedGemma inference utilities."""

from inference.agent_factory import create_react_agent
from inference.config import AgentConfig
from inference.model_factory import create_model_loader
from inference.schemas import (
    CriterionClassificationResult,
    FieldMappingResult,
    MedicalConceptsResult,
)

try:
    from inference.tools import (
        classify_criterion,
        extract_field_mapping,
        identify_medical_concepts,
    )
except ImportError:
    # Tools may not be available if langchain dependencies are missing
    classify_criterion = None  # type: ignore[assignment, misc]
    extract_field_mapping = None  # type: ignore[assignment, misc]
    identify_medical_concepts = None  # type: ignore[assignment, misc]

__all__ = [
    "AgentConfig",
    "create_model_loader",
    "create_react_agent",
    "FieldMappingResult",
    "CriterionClassificationResult",
    "MedicalConceptsResult",
    "extract_field_mapping",
    "classify_criterion",
    "identify_medical_concepts",
]

