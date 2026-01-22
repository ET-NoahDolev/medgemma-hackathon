"""Tests for grounding agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grounding_service.agent import GroundingAgent, get_grounding_agent
from grounding_service.schemas import FieldMappingResult, GroundingResult


@pytest.fixture
def mock_invoke():
    """Mock inference invoke function."""

    async def invoke(_prompt_vars):
        return GroundingResult(
            snomed_codes=["123456789"],
            field_mappings=[
                FieldMappingResult(
                    field="demographics.age",
                    relation=">=",
                    value="18",
                    confidence=0.9,
                    umls_cui="123456789",
                )
            ],
            reasoning="Test reasoning",
        )

    return invoke


@pytest.mark.asyncio
async def test_ground_returns_structured_result():
    """Test that ground() returns a structured GroundingResult."""
    mock_message = MagicMock()
    mock_message.content = (
        '{"snomed_codes": ["123456789"], "field_mappings": '
        '[{"field": "demographics.age", "relation": ">=", "value": "18", '
        '"confidence": 0.9, "umls_cui": "123456789"}], '
        '"reasoning": "Test reasoning"}'
    )
    # The agent is called directly with await, so it needs to be an AsyncMock
    mock_agent = AsyncMock(
        return_value=GroundingResult(
            snomed_codes=["123456789"],
            field_mappings=[
                FieldMappingResult(
                    field="demographics.age",
                    relation=">=",
                    value="18",
                    confidence=0.9,
                    umls_cui="123456789",
                )
            ],
            reasoning="Test reasoning",
        )
    )

    with patch("grounding_service.agent.ChatGoogleGenerativeAI"):
        with patch("inference.create_react_agent") as mock_create:
            mock_create.return_value = mock_agent
            agent = GroundingAgent()
            result = await agent.ground("Age >= 18", "inclusion")

            assert isinstance(result, GroundingResult)
            assert len(result.snomed_codes) > 0
            assert len(result.field_mappings) > 0
            assert result.field_mappings[0].field == "demographics.age"


@pytest.mark.asyncio
async def test_ground_fallback_on_invoke_error():
    """Test that ground() raises errors when agent invoke fails."""
    # The agent is called directly with await, so it needs to be an AsyncMock
    mock_agent = AsyncMock(side_effect=ValueError("Invalid JSON"))

    with patch("grounding_service.agent.ChatGoogleGenerativeAI"):
        with patch("inference.create_react_agent") as mock_create:
            mock_create.return_value = mock_agent
            agent = GroundingAgent()
            # Error should be raised, not caught
            with pytest.raises(ValueError, match="Invalid JSON"):
                await agent.ground("Age >= 18", "inclusion")


def test_get_grounding_agent_singleton():
    """Test that get_grounding_agent returns a singleton."""
    # Clear singleton
    import grounding_service.agent

    grounding_service.agent._agent_instance = None

    agent1 = get_grounding_agent()
    agent2 = get_grounding_agent()

    assert agent1 is agent2


@pytest.mark.asyncio
async def test_search_concepts_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the search_concepts_tool LangChain tool."""
    from grounding_service.agent import search_concepts_tool

    with patch("grounding_service.agent.UmlsClient") as mock_client_class:
        mock_client = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.code = "123456789"
        mock_candidate.display = "Test Concept"
        mock_candidate.ontology = "SNOMEDCT_US"
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.search_snomed.return_value = [mock_candidate]
        mock_client_class.return_value = mock_client

        monkeypatch.setenv("UMLS_API_KEY", "test-key")
        if hasattr(search_concepts_tool, "invoke"):
            result = search_concepts_tool.invoke({"term": "test", "limit": 5})
        else:
            # When LangChain isn't installed, our fallback @tool decorator is a no-op.
            result = search_concepts_tool(term="test", limit=5)

        import json

        data = json.loads(result)
        assert len(data) > 0
        assert data[0]["code"] == "123456789"


@pytest.mark.asyncio
async def test_get_semantic_type_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the get_semantic_type_tool LangChain tool."""
    from grounding_service.agent import get_semantic_type_tool

    with patch("grounding_service.agent.UmlsClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.get_semantic_types.return_value = ["T032", "T081"]
        mock_client_class.return_value = mock_client

        monkeypatch.setenv("UMLS_API_KEY", "test-key")
        if hasattr(get_semantic_type_tool, "invoke"):
            result = get_semantic_type_tool.invoke({"cui": "C123456"})
        else:
            result = get_semantic_type_tool(cui="C123456")

        import json

        data = json.loads(result)
        assert data["cui"] == "C123456"
        assert "T032" in data["semantic_types"]
        assert "T081" in data["semantic_types"]
