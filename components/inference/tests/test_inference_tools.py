"""Tests for MedGemma tools with Pydantic validation."""

from unittest.mock import MagicMock, patch

from inference.schemas import (
    CriterionClassificationResult,
    FieldMappingResult,
    MedicalConceptsResult,
)
from inference.tools import (
    classify_criterion,
    extract_field_mapping,
    identify_medical_concepts,
)


class TestExtractFieldMapping:
    """Tests for extract_field_mapping tool."""

    def test_extract_field_mapping_returns_valid_json(self) -> None:
        """Test that extract_field_mapping returns valid JSON."""
        mock_model = MagicMock()
        # Simulate structured output
        mock_result = FieldMappingResult(
            field_name="age",
            relation_type=">=",
            value="18",
            unit="years",
            confidence=0.95,
        )
        # with_structured_output returns a model that has invoke
        # which returns the result
        mock_structured_model = MagicMock()
        mock_structured_model.invoke.return_value = mock_result
        mock_model.with_structured_output.return_value = mock_structured_model

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            result = extract_field_mapping.invoke({"criterion_text": "Age >= 18 years"})

            assert isinstance(result, str)
            # Validate it's valid JSON that can be parsed back
            parsed = FieldMappingResult.model_validate_json(result)
            assert parsed.field_name == "age"
            assert parsed.relation_type == ">="
            assert parsed.value == "18"
            assert parsed.unit == "years"
            assert parsed.confidence == 0.95

    def test_extract_field_mapping_fallback_to_parser(self) -> None:
        """Test fallback to PydanticOutputParser when with_structured_output fails."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            '{"field_name": "bmi", "relation_type": "<", '
            '"value": "30", "unit": "kg/m²", "confidence": 0.9}'
        )
        mock_model.with_structured_output.side_effect = AttributeError("Not supported")
        mock_model.invoke.return_value = mock_response

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            result = extract_field_mapping.invoke({"criterion_text": "BMI < 30 kg/m²"})

            assert isinstance(result, str)
            parsed = FieldMappingResult.model_validate_json(result)
            assert parsed.field_name == "bmi"
            assert parsed.relation_type == "<"

    def test_extract_field_mapping_handles_errors(self) -> None:
        """Test that extract_field_mapping handles errors gracefully."""
        mock_model = MagicMock()
        mock_model.with_structured_output.side_effect = Exception("Model error")
        mock_model.invoke.side_effect = Exception("Model error")

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            result = extract_field_mapping.invoke({"criterion_text": "Age >= 18"})

            assert isinstance(result, str)
            # Should return error JSON
            assert "error" in result.lower() or "null" in result


class TestClassifyCriterion:
    """Tests for classify_criterion tool."""

    def test_classify_criterion_returns_valid_json(self) -> None:
        """Test that classify_criterion returns valid JSON."""
        mock_model = MagicMock()
        mock_result = CriterionClassificationResult(
            criterion_type="inclusion",
            confidence=0.92,
            reasoning="Age requirement is an inclusion criterion",
        )
        # with_structured_output returns a model that has invoke
        # which returns the result
        mock_structured_model = MagicMock()
        mock_structured_model.invoke.return_value = mock_result
        mock_model.with_structured_output.return_value = mock_structured_model

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            result = classify_criterion.invoke({"criterion_text": "Age >= 18 years"})

            assert isinstance(result, str)
            parsed = CriterionClassificationResult.model_validate_json(result)
            assert parsed.criterion_type == "inclusion"
            assert parsed.confidence == 0.92
            assert "Age requirement" in parsed.reasoning

    def test_classify_criterion_handles_exclusion(self) -> None:
        """Test classification of exclusion criteria."""
        mock_model = MagicMock()
        mock_result = CriterionClassificationResult(
            criterion_type="exclusion",
            confidence=0.88,
            reasoning="Pregnancy is an exclusion criterion",
        )
        # with_structured_output returns a model that has invoke
        # which returns the result
        mock_structured_model = MagicMock()
        mock_structured_model.invoke.return_value = mock_result
        mock_model.with_structured_output.return_value = mock_structured_model

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            result = classify_criterion.invoke(
                {"criterion_text": "Pregnant or breastfeeding"}
            )

            parsed = CriterionClassificationResult.model_validate_json(result)
            assert parsed.criterion_type == "exclusion"

    def test_classify_criterion_handles_errors(self) -> None:
        """Test that classify_criterion handles errors gracefully."""
        mock_model = MagicMock()
        mock_model.with_structured_output.side_effect = Exception("Model error")

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            result = classify_criterion.invoke({"criterion_text": "Age >= 18"})

            assert isinstance(result, str)
            # Should return error JSON with default values
            assert "error" in result.lower() or "inclusion" in result.lower()


class TestIdentifyMedicalConcepts:
    """Tests for identify_medical_concepts tool."""

    def test_identify_medical_concepts_returns_valid_json(self) -> None:
        """Test that identify_medical_concepts returns valid JSON."""
        mock_model = MagicMock()
        mock_result = MedicalConceptsResult(
            concepts=["diabetes", "HbA1c", "glucose"],
            interpretation="Diabetes-related concepts requiring UMLS grounding",
        )
        # with_structured_output returns a model that has invoke
        # which returns the result
        mock_structured_model = MagicMock()
        mock_structured_model.invoke.return_value = mock_result
        mock_model.with_structured_output.return_value = mock_structured_model

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            result = identify_medical_concepts.invoke(
                {"text": "HbA1c < 7.0% indicates well-controlled diabetes"}
            )

            assert isinstance(result, str)
            parsed = MedicalConceptsResult.model_validate_json(result)
            assert len(parsed.concepts) == 3
            assert "diabetes" in parsed.concepts
            assert "HbA1c" in parsed.concepts
            assert "glucose" in parsed.concepts
            assert "UMLS" in parsed.interpretation

    def test_identify_medical_concepts_handles_empty_concepts(self) -> None:
        """Test handling of text with no medical concepts."""
        mock_model = MagicMock()
        mock_result = MedicalConceptsResult(
            concepts=[],
            interpretation="No specific medical concepts identified",
        )
        # with_structured_output returns a model that has invoke
        # which returns the result
        mock_structured_model = MagicMock()
        mock_structured_model.invoke.return_value = mock_result
        mock_model.with_structured_output.return_value = mock_structured_model

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            result = identify_medical_concepts.invoke({"text": "This is general text"})

            parsed = MedicalConceptsResult.model_validate_json(result)
            assert parsed.concepts == []
            assert isinstance(parsed.interpretation, str)

    def test_identify_medical_concepts_handles_errors(self) -> None:
        """Test that identify_medical_concepts handles errors gracefully."""
        mock_model = MagicMock()
        mock_model.with_structured_output.side_effect = Exception("Model error")

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            result = identify_medical_concepts.invoke(
                {"text": "Diabetes mellitus type 2"}
            )

            assert isinstance(result, str)
            # Should return error JSON
            assert "error" in result.lower() or "concepts" in result.lower()
