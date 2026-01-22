"""Tests for grounding service tools."""

from unittest.mock import MagicMock, patch

import pytest

from grounding_service.tools import interpret_medical_text


@pytest.mark.asyncio
async def test_interpret_medical_text_calls_medgemma() -> None:
    """Test that interpret_medical_text calls MedGemma model."""
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"concepts": ["diabetes"], "thresholds": []}'
    mock_model.invoke.return_value = mock_response

    with patch("inference.create_model_loader") as mock_loader:
        mock_loader.return_value = lambda: mock_model
        result = interpret_medical_text.invoke(
            {"text": "Age >= 18 years", "context": "criterion"}
        )

        assert isinstance(result, str)
        mock_model.invoke.assert_called_once()
        call_args = mock_model.invoke.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0][0] == "user"


@pytest.mark.asyncio
async def test_interpret_medical_text_handles_errors() -> None:
    """Test that interpret_medical_text handles errors gracefully."""
    mock_model = MagicMock()
    mock_model.invoke.side_effect = Exception("Model error")

    with patch("inference.create_model_loader") as mock_loader:
        mock_loader.return_value = lambda: mock_model
        # Should not raise, but may return error message
        result = interpret_medical_text.invoke(
            {"text": "Age >= 18", "context": "criterion"}
        )
        assert isinstance(result, str)
