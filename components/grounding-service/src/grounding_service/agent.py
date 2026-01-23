"""LangGraph ReAct agent for grounding clinical trial criteria."""

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    from langchain_core.tools import tool  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    # Minimal fallback so this module can be imported without LangChain installed.
    def _tool(func=None, **_kwargs):  # type: ignore[no-redef]
        if func is None:
            return lambda f: f
        return func

    tool = _tool  # type: ignore[assignment]

if TYPE_CHECKING:
    from langchain_google_genai import ChatGoogleGenerativeAI as ChatGoogleGenerativeAI
else:
    try:
        from langchain_google_genai import (
            ChatGoogleGenerativeAI as ChatGoogleGenerativeAI,
        )
    except ImportError:  # pragma: no cover
        ChatGoogleGenerativeAI = object  # type: ignore[assignment]

from grounding_service.schemas import GroundingResult
from grounding_service.tools import interpret_medical_text
from grounding_service.umls_client import UmlsClient

logger = logging.getLogger(__name__)


# LangChain tools wrapping UMLS client
# Note: These tools use UmlsClient directly. The MCP server (mcp_server.py)
# provides the same functionality via FastMCP for external MCP protocol clients.
# Both implementations use the same underlying UmlsClient, ensuring consistency.
@tool
def search_concepts_tool(term: str, limit: int = 5) -> str:
    """Search UMLS for clinical concepts matching a term.

    Args:
        term: Clinical term or phrase to search for.
        limit: Maximum number of results to return (default: 5).

    Returns:
        JSON string with list of concepts containing UMLS CUI and SNOMED code.
    """
    import json

    api_key = os.getenv("UMLS_API_KEY")
    if not api_key:
        return json.dumps([])

    try:
        with UmlsClient(api_key=api_key) as client:
            candidates = client.search_snomed(term, limit)
            results = [
                {
                    "snomed_code": c.code,
                    "display": c.display,
                    "cui": c.cui,
                    "ontology": c.ontology,
                }
                for c in candidates
            ]
            return json.dumps(results)
    except Exception as e:
        logger.error("Error in search_concepts_tool: %s", e)
        return json.dumps([])


@tool
def get_semantic_type_tool(cui: str) -> str:
    """Get semantic type information for a UMLS concept.

    Args:
        cui: UMLS Concept Unique Identifier.

    Returns:
        JSON string with semantic types (TUIs) for the concept.
    """
    import json

    api_key = os.getenv("UMLS_API_KEY")
    if not api_key:
        return json.dumps({"cui": cui, "semantic_types": []})

    try:
        with UmlsClient(api_key=api_key) as client:
            tuis = client.get_semantic_types(cui)
            return json.dumps({"cui": cui, "semantic_types": tuis})
    except Exception as e:
        logger.error("Error in get_semantic_type_tool: %s", e)
        return json.dumps({"cui": cui, "semantic_types": []})


class GroundingAgent:
    """LangGraph ReAct agent for grounding clinical trial criteria.

    Uses Gemini 2.5 Pro as orchestrator with:
    - MedGemma tool for medical interpretation
    - UMLS MCP tools for code lookups
    """

    def __init__(
        self,
        model_path: str | None = None,
        quantization: str = "4bit",
    ) -> None:
        """Initialize the grounding agent.

        Args:
            model_path: Path to MedGemma model (unused, kept for compatibility).
            quantization: Quantization level (unused, kept for compatibility).
        """
        self._agent: Any | None = None

    async def _get_agent(self) -> Any:
        """Get or create the Gemini orchestrator agent with structured output."""
        if self._agent is not None:
            return self._agent

        from inference import create_react_agent
        from inference.model_factory import create_gemini_model_loader

        from grounding_service.schemas import GroundingResult

        tools = [interpret_medical_text, search_concepts_tool, get_semantic_type_tool]

        gemini_loader = create_gemini_model_loader()

        prompts_dir = Path(__file__).parent / "prompts"

        # Create agent with GroundingResult schema enforced
        self._agent = create_react_agent(
            model_loader=gemini_loader,
            prompts_dir=prompts_dir,
            tools=tools,
            response_schema=GroundingResult,  # Pydantic schema
            system_template="grounding_system.j2",
            user_template="grounding_user.j2",
        )
        return self._agent

    async def ground(
        self, criterion_text: str, criterion_type: str
    ) -> GroundingResult:
        """Ground a criterion using Gemini orchestrator with structured output.

        Args:
            criterion_text: The criterion text to ground.
            criterion_type: Type of criterion ("inclusion" or "exclusion").

        Returns:
            GroundingResult with SNOMED codes and field mappings.
        """
        agent = await self._get_agent()
        return await agent(
            {
                "criterion_text": criterion_text,
                "criterion_type": criterion_type,
            }
        )


# Singleton instance
_agent_instance: GroundingAgent | None = None


def get_grounding_agent() -> GroundingAgent:
    """Get or create singleton grounding agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GroundingAgent()
    return _agent_instance
