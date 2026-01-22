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
except ImportError:  # pragma: no cover
    # Minimal fallback so this module can be imported without LangChain installed.
    def _tool(func=None, **_kwargs):  # type: ignore[no-redef]
        if func is None:
            return lambda f: f
        return func

    tool = _tool  # type: ignore[assignment]
    ChatGoogleGenerativeAI = None  # type: ignore[assignment,misc]
    MultiServerMCPClient = None  # type: ignore[assignment,misc]

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
    # Don't set experiment at module import time - it may not exist or may be deleted.
    # The experiment will be set lazily when needed in the ground() method.
    # This prevents import-time failures during tests.
except ImportError:
    mlflow = None
    MLFLOW_AVAILABLE = False
except Exception:
    # Handle any other MLflow initialization errors gracefully
    # (e.g., if set_tracking_uri fails) - fail silently at import time
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
        """Get or create the Gemini orchestrator agent with structured output."""
        if self._agent is not None:
            return self._agent

        from inference import create_react_agent

        from grounding_service.schemas import GroundingResult

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

        # Create Gemini model loader
        def gemini_loader():
            from langchain_google_genai import ChatGoogleGenerativeAI

            gemini_model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-pro")
            project_id = os.getenv("GCP_PROJECT_ID")
            region = os.getenv("GCP_REGION", "europe-west4")

            if ChatGoogleGenerativeAI is None:
                raise ImportError("langchain-google-genai is required")

            return ChatGoogleGenerativeAI(
                model=gemini_model_name,
                project=project_id,
                location=region,
                vertexai=True,
            )

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

    async def _ground_with_tracing(
        self,
        agent: Any,
        criterion_text: str,
        criterion_type: str,
        start_time: float,
    ) -> GroundingResult:
        """Ground with MLflow tracing support.

        Args:
            agent: The agent to invoke.
            criterion_text: The criterion text to ground.
            criterion_type: Type of criterion ("inclusion" or "exclusion").
            start_time: Start time for latency calculation.

        Returns:
            GroundingResult with SNOMED codes and field mappings.
        """
        assert mlflow is not None  # Type narrowing for mypy
        with mlflow.tracing.start_trace(name="grounding_agent"):
            # Add custom metadata if API supports it
            try:
                if hasattr(mlflow.tracing, "set_tag"):
                    mlflow.tracing.set_tag("criterion_type", criterion_type)
                    gemini_model = os.getenv(
                        "GEMINI_MODEL_NAME", "gemini-2.5-pro"
                    )
                    mlflow.tracing.set_tag("orchestrator_model", gemini_model)
            except Exception as e:
                logger.debug("Failed to set trace tags: %s", e)

            # Invoke - autologging will automatically trace this
            result = await agent(
                {
                    "criterion_text": criterion_text,
                    "criterion_type": criterion_type,
                }
            )

            # Log custom metrics if API supports it
            try:
                duration = time.time() - start_time
                if hasattr(mlflow.tracing, "set_metric"):
                    mlflow.tracing.set_metric("latency_seconds", duration)
                    mlflow.tracing.set_metric(
                        "snomed_codes_count", len(result.snomed_codes)
                    )
                    mlflow.tracing.set_metric(
                        "field_mappings_count", len(result.field_mappings)
                    )
            except Exception as e:
                logger.debug("Failed to log trace metrics: %s", e)

            return result

    async def _ground_with_runs(
        self,
        agent: Any,
        criterion_text: str,
        criterion_type: str,
        start_time: float,
    ) -> GroundingResult:
        """Ground with MLflow run-based logging.

        Args:
            agent: The agent to invoke.
            criterion_text: The criterion text to ground.
            criterion_type: Type of criterion ("inclusion" or "exclusion").
            start_time: Start time for latency calculation.

        Returns:
            GroundingResult with SNOMED codes and field mappings.
        """
        assert mlflow is not None  # Type narrowing for mypy
        with mlflow.start_run(run_name="grounding_agent", nested=True):
            mlflow.log_params(
                {
                    "criterion_text": criterion_text[:200],  # Truncate
                    "criterion_type": criterion_type,
                    "orchestrator_model": os.getenv(
                        "GEMINI_MODEL_NAME", "gemini-2.5-pro"
                    ),
                }
            )

            result = await agent(
                {
                    "criterion_text": criterion_text,
                    "criterion_type": criterion_type,
                }
            )

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

    async def _ground_without_mlflow(
        self, agent: Any, criterion_text: str, criterion_type: str
    ) -> GroundingResult:
        """Ground without MLflow logging.

        Args:
            agent: The agent to invoke.
            criterion_text: The criterion text to ground.
            criterion_type: Type of criterion ("inclusion" or "exclusion").

        Returns:
            GroundingResult with SNOMED codes and field mappings.
        """
        return await agent(
            {
                "criterion_text": criterion_text,
                "criterion_type": criterion_type,
            }
        )

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
        start_time = time.time()

        if not (MLFLOW_AVAILABLE and mlflow is not None):
            return await self._ground_without_mlflow(
                agent, criterion_text, criterion_type
            )

        # Set experiment lazily when needed (not at import time to avoid failures)
        try:
            mlflow.set_experiment("medgemma-grounding")
        except Exception as e:
            # If experiment is deleted or doesn't exist, continue without MLflow
            logger.debug("Failed to set MLflow experiment (non-fatal): %s", e)
            return await self._ground_without_mlflow(
                agent, criterion_text, criterion_type
            )

        # Try to use trace-based approach if available, otherwise fall back to runs
        # Autologging will handle detailed tracing of agent calls automatically
        try:
            has_tracing = (
                hasattr(mlflow, "tracing")
                and hasattr(mlflow.tracing, "start_trace")
            )
            if has_tracing:
                return await self._ground_with_tracing(
                    agent, criterion_text, criterion_type, start_time
                )
            raise AttributeError("Tracing API not available")
        except (AttributeError, Exception) as e:
            # Fallback to run-based logging
            logger.debug("MLflow tracing not available, using runs: %s", e)
            try:
                return await self._ground_with_runs(
                    agent, criterion_text, criterion_type, start_time
                )
            except Exception as e:
                logger.warning("MLflow logging failed (non-fatal): %s", e)
                # Continue without MLflow if all logging fails
                return await self._ground_without_mlflow(
                    agent, criterion_text, criterion_type
                )


# Singleton instance
_agent_instance: GroundingAgent | None = None


def get_grounding_agent() -> GroundingAgent:
    """Get or create singleton grounding agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GroundingAgent()
    return _agent_instance
