"""Tests for MedGemma tools returning raw text."""

from unittest.mock import MagicMock, patch

import pytest

from inference.tools import (
    classify_criterion,
    extract_field_mapping,
    identify_medical_concepts,
)


class TestExtractFieldMapping:
    """Tests for extract_field_mapping tool."""

    def test_extract_field_mapping_returns_text(self) -> None:
        """Test that extract_field_mapping returns raw text."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "field: age, relation: >=, value: 18 years"
        mock_model.invoke.return_value = mock_response

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            result = extract_field_mapping.invoke({"criterion_text": "Age >= 18 years"})

            assert isinstance(result, str)
            assert "age" in result.lower()

    def test_extract_field_mapping_raises_on_error(self) -> None:
        """Test that extract_field_mapping raises on model errors."""
        mock_model = MagicMock()
        mock_model.invoke.side_effect = Exception("Model error")

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            with pytest.raises(Exception, match="Model error"):
                extract_field_mapping.invoke({"criterion_text": "Age >= 18"})


class TestClassifyCriterion:
    """Tests for classify_criterion tool."""

    def test_classify_criterion_returns_text(self) -> None:
        """Test that classify_criterion returns raw text."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "inclusion: age requirement"
        mock_model.invoke.return_value = mock_response

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            result = classify_criterion.invoke({"criterion_text": "Age >= 18 years"})

            assert isinstance(result, str)
            assert "inclusion" in result.lower()

    def test_classify_criterion_raises_on_error(self) -> None:
        """Test that classify_criterion raises on model errors."""
        mock_model = MagicMock()
        mock_model.invoke.side_effect = Exception("Model error")

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            with pytest.raises(Exception, match="Model error"):
                classify_criterion.invoke({"criterion_text": "Age >= 18"})


class TestIdentifyMedicalConcepts:
    """Tests for identify_medical_concepts tool."""

    def test_identify_medical_concepts_returns_text(self) -> None:
        """Test that identify_medical_concepts returns raw text."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Concepts: diabetes, HbA1c, glucose"
        mock_model.invoke.return_value = mock_response

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            result = identify_medical_concepts.invoke(
                {"text": "HbA1c < 7.0% indicates well-controlled diabetes"}
            )

            assert isinstance(result, str)
            assert "diabetes" in result.lower()

    def test_identify_medical_concepts_raises_on_error(self) -> None:
        """Test that identify_medical_concepts raises on model errors."""
        mock_model = MagicMock()
        mock_model.invoke.side_effect = Exception("Model error")

        with patch("inference.create_model_loader") as mock_loader, patch(
            "inference.AgentConfig"
        ) as mock_config:
            mock_config.from_env.return_value = MagicMock()
            mock_loader.return_value = lambda: mock_model
            with pytest.raises(Exception, match="Model error"):
                identify_medical_concepts.invoke({"text": "Diabetes mellitus type 2"})
