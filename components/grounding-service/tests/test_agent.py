"""Tests for grounding agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grounding_service.agent import GroundingAgent, get_grounding_agent
from grounding_service.schemas import GroundedTerm, GroundingResult


@pytest.fixture
def mock_invoke():
    """Mock inference invoke function."""

    async def invoke(_prompt_vars):
        return GroundingResult(
            terms=[
                GroundedTerm(
                    snippet="Age >= 18",
                    raw_criterion_text="Age >= 18",
                    criterion_type="inclusion",
                    snomed_code="123456789",
                    relation=">=",
                    value="18",
                    confidence=0.9,
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
        '{"terms": [{"snippet": "Age >= 18", "snomed_code": "123456789", '
        '"relation": ">=", "value": "18", "confidence": 0.9}], '
        '"reasoning": "Test reasoning"}'
    )
    # The agent is called directly with await, so it needs to be an AsyncMock
    mock_agent = AsyncMock(
        return_value=GroundingResult(
            terms=[
                GroundedTerm(
                    snippet="Age >= 18",
                    raw_criterion_text="Age >= 18",
                    criterion_type="inclusion",
                    snomed_code="123456789",
                    relation=">=",
                    value="18",
                    confidence=0.9,
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
            assert len(result.terms) > 0
            assert result.terms[0].snomed_code == "123456789"
            assert result.terms[0].relation == ">="
            assert result.terms[0].value == "18"


@pytest.mark.asyncio
async def test_ground_fallback_on_invoke_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that ground() raises errors when agent invoke fails."""
    async def failing_invoke(*_args: object, **_kwargs: object) -> None:
        raise ValueError("Invalid JSON")

    monkeypatch.setenv("ENABLE_GROUNDING_SEMANTIC_CACHE", "false")

    with patch("grounding_service.agent.ChatGoogleGenerativeAI"):
        with patch("inference.create_react_agent") as mock_create:
            mock_create.return_value = failing_invoke
            agent = GroundingAgent()
            agent._agent = None  # force _get_agent to run under the patch
            # Error should be raised, not caught
            with pytest.raises(ValueError, match="Invalid JSON"):
                await agent.ground("Age >= 18", "inclusion")


@pytest.mark.asyncio
async def test_ground_uses_cache_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached = GroundingResult(
        terms=[
            GroundedTerm(
                snippet="Hypertension",
                raw_criterion_text="Hypertension",
                criterion_type="inclusion",
                snomed_code="123",
                relation="=",
                value="Hypertension",
                confidence=0.8,
            )
        ],
        reasoning="cached",
    )

    class DummyCache:
        def get(self, _text: str) -> tuple[GroundingResult | None, float]:
            return cached, 0.99

        def set(self, _text: str, _result: GroundingResult) -> None:
            raise AssertionError("Cache set should not be called on hit")

    monkeypatch.setenv("ENABLE_GROUNDING_SEMANTIC_CACHE", "true")
    monkeypatch.setattr("grounding_service.agent.get_grounding_cache", DummyCache)

    agent = GroundingAgent()
    agent._get_agent = AsyncMock()

    result = await agent.ground("Hypertension", "inclusion")
    assert result == cached
    agent._get_agent.assert_not_awaited()


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
        from grounding_service.umls_client import SnomedCandidate

        mock_client = MagicMock()
        mock_candidate = SnomedCandidate(
            code="123456789",
            display="Test Concept",
            cui="C123456",
            ontology="SNOMEDCT_US",
            confidence=0.9,
        )
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
        assert data[0]["snomed_code"] == "123456789"
        assert data[0]["display"] == "Test Concept"


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
