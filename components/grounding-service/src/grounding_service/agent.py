"""LangGraph ReAct agent for grounding clinical trial criteria."""

import logging
import os
import time
from pathlib import Path
from typing import Any

from dotenv import find_dotenv

try:
    from langchain_core.tools import tool  # type: ignore[import-not-found]
    from langchain_google_genai import (
        ChatGoogleGenerativeAI,  # type: ignore[import-not-found]
    )
    from langchain_mcp_adapters.client import (  # type: ignore[import-not-found]
        MultiServerMCPClient,
    )
    from langgraph.prebuilt import create_react_agent  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    # Minimal fallback so this module can be imported without LangChain installed.
    def _tool(func=None, **_kwargs):  # type: ignore[no-redef]
        if func is None:
            return lambda f: f
        return func

    tool = _tool  # type: ignore[assignment]
    ChatGoogleGenerativeAI = None  # type: ignore[assignment,misc]
    MultiServerMCPClient = None  # type: ignore[assignment,misc]
    create_react_agent = None  # type: ignore[assignment,misc]

from shared.field_schema import SEMANTIC_TYPE_MAPPING

from grounding_service.schemas import GroundingResult
from grounding_service.tools import interpret_medical_text
from grounding_service.umls_client import UmlsClient


# Try to import mlflow (optional dependency for dev/observability)
def _get_mlflow_tracking_uri() -> str:
    """Get the MLflow tracking URI using absolute path to SQLite database.

    Raises:
        RuntimeError: If .env file cannot be found to determine repo root.
    """
    # Find repo root by looking for .env file (find_dotenv walks up to find it)
    env_path = find_dotenv()
    if not env_path:
        raise RuntimeError(
            "Cannot determine repo root: .env file not found. "
            "Please ensure you're running from the repository root or have a .env file."
        )
    repo_root = Path(env_path).parent.absolute()
    db_path = repo_root / "mlflow.db"
    return f"sqlite:///{db_path}"


# Set environment variable before import so MLflow reads it during initialization
_mlflow_uri = _get_mlflow_tracking_uri()
os.environ.setdefault("MLFLOW_TRACKING_URI", _mlflow_uri)
mlflow: Any | None
try:
    import mlflow as _mlflow
    MLFLOW_AVAILABLE = True
    # database backend (SQLite) with absolute path
    mlflow = _mlflow
    mlflow.set_tracking_uri(_mlflow_uri)
    mlflow.set_experiment("medgemma-grounding")
except ImportError:
    mlflow = None
    MLFLOW_AVAILABLE = False

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
        JSON string with list of concepts containing code, display, and cui.
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
                    "code": c.code,
                    "display": c.display,
                    "cui": c.code,
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
        """Get or create the Gemini orchestrator agent with tools."""
        if self._agent is not None:
            return self._agent

        if create_react_agent is None:
            raise ImportError(
                "langgraph and langchain-google-genai are required for grounding agent"
            )

        # Get UMLS tools via MCP
        mcp_tools: list[Any] = []
        if MultiServerMCPClient is not None:
            try:
                mcp_client = MultiServerMCPClient(
                    {
                        "umls": {
                            "transport": "stdio",
                            "command": "python",
                            "args": ["-m", "grounding_service.mcp_server"],
                        }
                    }
                )
                mcp_tools = await mcp_client.get_tools()
            except Exception as e:
                logger.warning("Failed to load UMLS MCP tools: %s", e)
                # Fallback to direct UMLS tools
                mcp_tools = [search_concepts_tool, get_semantic_type_tool]

        # Combine with MedGemma tool
        tools = [interpret_medical_text, *mcp_tools]

        # Gemini 2.5 Pro as orchestrator (supports tool calling)
        gemini_model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-pro")
        project_id = os.getenv("GCP_PROJECT_ID")
        region = os.getenv("GCP_REGION", "europe-west4")

        if ChatGoogleGenerativeAI is None:
            raise ImportError("langchain-google-genai is required")

        model = ChatGoogleGenerativeAI(
            model=gemini_model_name,
            project=project_id,
            location=region,
            vertexai=True,  # Use Vertex AI backend
        )

        # Create agent with tools
        self._agent = create_react_agent(model=model, tools=tools)
        return self._agent

    async def ground(
        self, criterion_text: str, criterion_type: str
    ) -> GroundingResult:
        """Ground a criterion using the Gemini orchestrator agent.

        Args:
            criterion_text: The criterion text to ground.
            criterion_type: Type of criterion ("inclusion" or "exclusion").

        Returns:
            GroundingResult with SNOMED codes and field mappings.
        """
        agent = await self._get_agent()

        # Build prompt for Gemini orchestrator
        prompt = f"""Ground this clinical trial criterion:

Criterion: {criterion_text}
Type: {criterion_type}

Use the available tools to:
1. Call interpret_medical_text to get MedGemma's clinical interpretation
2. For each identified concept, call search_concepts to find UMLS matches
3. Call get_semantic_type to determine field categories
4. Map semantic types to field categories using: {SEMANTIC_TYPE_MAPPING}
5. Return a structured GroundingResult with SNOMED codes and field mappings

Always use MedGemma for medical interpretation - it has specialized medical knowledge.
Use UMLS tools for code lookups - they have the terminology database."""

        async def _safe_invoke() -> GroundingResult:
            try:
                result = await agent.ainvoke(
                    {"messages": [("user", prompt)]}
                )
                # Parse result - LangGraph returns messages
                if isinstance(result, dict) and "messages" in result:
                    messages = result["messages"]
                    if messages:
                        last_msg = messages[-1]
                        content = getattr(last_msg, "content", "")
                        # Try to parse as JSON or extract structured data
                        import json

                        try:
                            # Look for JSON in content
                            start = content.find("{")
                            end = content.rfind("}") + 1
                            if start >= 0 and end > start:
                                data = json.loads(content[start:end])
                                return GroundingResult(**data)
                        except (json.JSONDecodeError, TypeError, ValueError):
                            pass

                # Fallback: return empty result with reasoning
                return GroundingResult(
                    snomed_codes=[],
                    field_mappings=[],
                    reasoning=content if isinstance(result, dict) else str(result),
                )
            except Exception as exc:
                logger.warning("Grounding agent failed: %s", exc, exc_info=True)
                return GroundingResult(
                    snomed_codes=[],
                    field_mappings=[],
                    reasoning=(
                        "Agent execution completed but structured output not available"
                    ),
                )

        # MLflow instrumentation
        if MLFLOW_AVAILABLE and mlflow is not None:
            with mlflow.start_run(run_name="grounding_agent"):
                mlflow.log_params(
                    {
                        "criterion_text": criterion_text[:200],  # Truncate
                        "criterion_type": criterion_type,
                        "orchestrator_model": os.getenv(
                            "GEMINI_MODEL_NAME", "gemini-2.5-pro"
                        ),
                    }
                )

                start_time = time.time()
                result = await _safe_invoke()
                try:
                    duration = time.time() - start_time
                    mlflow.log_metrics(
                        {
                            "latency_seconds": duration,
                            "snomed_codes_count": len(result.snomed_codes),
                            "field_mappings_count": len(result.field_mappings),
                        }
                    )
                    mlflow.log_text(result.reasoning, "reasoning.txt")
                except Exception as e:
                    mlflow.log_param("error", str(e))
                    raise e
                return result
        else:
            return await _safe_invoke()


# Singleton instance
_agent_instance: GroundingAgent | None = None


def get_grounding_agent() -> GroundingAgent:
    """Get or create singleton grounding agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GroundingAgent()
    return _agent_instance
