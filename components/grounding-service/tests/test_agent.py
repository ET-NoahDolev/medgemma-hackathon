"""Tests for grounding agent."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grounding_service.agent import GroundingAgent, get_grounding_agent
from grounding_service.schemas import FieldMappingResult, GroundingResult


@pytest.fixture
def mock_model():
    """Mock ChatHuggingFace model."""
    model = MagicMock()
    return model


@pytest.fixture
def mock_agent_graph():
    """Mock LangGraph agent."""
    agent = AsyncMock()
    agent.ainvoke = AsyncMock(
        return_value={
            "structured_response": GroundingResult(
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
        }
    )
    return agent


@pytest.mark.asyncio
async def test_ground_returns_structured_result(mock_agent_graph):
    """Test that ground() returns a structured GroundingResult."""
    with patch("grounding_service.agent.create_react_agent") as mock_create:
        mock_create.return_value = mock_agent_graph

        agent = GroundingAgent(model_path="test-model", quantization="none")
        agent._get_agent = lambda: mock_agent_graph

        result = await agent.ground("Age >= 18", "inclusion")

        assert isinstance(result, GroundingResult)
        assert len(result.snomed_codes) > 0
        assert len(result.field_mappings) > 0
        assert result.field_mappings[0].field == "demographics.age"


@pytest.mark.asyncio
async def test_ground_fallback_on_parse_error(mock_agent_graph):
    """Test that ground() handles parse errors gracefully."""
    mock_agent_graph.ainvoke = AsyncMock(
        return_value={"messages": [MagicMock(content="Invalid JSON")]}
    )

    with patch("grounding_service.agent.create_react_agent") as mock_create:
        mock_create.return_value = mock_agent_graph

        agent = GroundingAgent(model_path="test-model", quantization="none")
        agent._get_agent = lambda: mock_agent_graph

        result = await agent.ground("Age >= 18", "inclusion")

        assert isinstance(result, GroundingResult)
        assert result.snomed_codes == []
        assert "not available" in result.reasoning


def test_get_grounding_agent_singleton():
    """Test that get_grounding_agent returns a singleton."""
    # Clear singleton
    import grounding_service.agent

    grounding_service.agent._agent_instance = None

    agent1 = get_grounding_agent()
    agent2 = get_grounding_agent()

    assert agent1 is agent2


@pytest.mark.asyncio
async def test_search_concepts_tool():
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

        os.environ["UMLS_API_KEY"] = "test-key"
        result = search_concepts_tool.invoke({"term": "test", "limit": 5})

        import json

        data = json.loads(result)
        assert len(data) > 0
        assert data[0]["code"] == "123456789"


@pytest.mark.asyncio
async def test_get_semantic_type_tool():
    """Test the get_semantic_type_tool LangChain tool."""
    from grounding_service.agent import get_semantic_type_tool

    with patch("grounding_service.agent.UmlsClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.get_semantic_types.return_value = ["T032", "T081"]
        mock_client_class.return_value = mock_client

        os.environ["UMLS_API_KEY"] = "test-key"
        result = get_semantic_type_tool.invoke({"cui": "C123456"})

        import json

        data = json.loads(result)
        assert data["cui"] == "C123456"
        assert "T032" in data["semantic_types"]
        assert "T081" in data["semantic_types"]
