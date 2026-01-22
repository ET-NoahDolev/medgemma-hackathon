"""LangGraph ReAct agent for grounding clinical trial criteria."""

import logging
import os
import time
from pathlib import Path
from typing import Any

from inference import AgentConfig, create_model_loader, create_react_agent

try:
    from langchain_core.tools import tool  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    # Minimal fallback so this module can be imported without LangChain installed.
    def _tool(func=None, **_kwargs):  # type: ignore[no-redef]
        if func is None:
            return lambda f: f
        return func

    tool = _tool  # type: ignore[assignment]

from shared.field_schema import SEMANTIC_TYPE_MAPPING

from grounding_service.schemas import GroundingResult
from grounding_service.umls_client import UmlsClient

# Try to import mlflow (optional dependency for dev/observability)
# Set environment variable before import so MLflow reads it during initialization
os.environ.setdefault("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
mlflow: Any | None
try:
    import mlflow as _mlflow
    MLFLOW_AVAILABLE = True
    # database backend (SQLite)
    mlflow = _mlflow
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
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
    """LangGraph ReAct agent for grounding clinical trial criteria."""

    def __init__(
        self,
        model_path: str | None = None,
        quantization: str = "4bit",
    ) -> None:
        """Initialize the grounding agent.

        Args:
            model_path: Path to MedGemma model or HuggingFace model ID.
            quantization: Quantization level ("4bit", "8bit", or "none").
        """
        default_model = os.getenv("MEDGEMMA_MODEL_PATH", "google/medgemma-1.5-4b-it")
        self.model_path = model_path or default_model
        self.quantization = quantization or os.getenv("MEDGEMMA_QUANTIZATION", "4bit")
        self._invoke: Any | None = None

    def _get_invoke(self) -> Any:
        """Get or create the shared inference invoke function."""
        if self._invoke is not None:
            return self._invoke

        cfg = AgentConfig(model_path=self.model_path, quantization=self.quantization)
        model_loader = create_model_loader(cfg)
        prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")
        self._invoke = create_react_agent(
            model_loader=model_loader,
            prompts_dir=Path(prompts_dir),
            tools=[search_concepts_tool, get_semantic_type_tool],
            response_schema=GroundingResult,
            system_template="grounding_system.j2",
            user_template="grounding_user.j2",
        )
        return self._invoke

    async def ground(
        self, criterion_text: str, criterion_type: str
    ) -> GroundingResult:
        """Ground a criterion using the ReAct agent.

        Args:
            criterion_text: The criterion text to ground.
            criterion_type: Type of criterion ("inclusion" or "exclusion").

        Returns:
            GroundingResult with SNOMED codes and field mappings.
        """
        invoke = self._get_invoke()
        prompt_vars = {
            "semantic_mappings": SEMANTIC_TYPE_MAPPING,
            "criterion_text": criterion_text,
            "criterion_type": criterion_type,
        }

        async def _safe_invoke() -> GroundingResult:
            try:
                return await invoke(prompt_vars)
            except Exception as exc:
                logger.warning("Grounding agent failed: %s", exc)
                return GroundingResult(
                    snomed_codes=[],
                    field_mappings=[],
                    reasoning=(
                        "Agent execution completed but structured output not available"
                    ),
                )

        # MLflow instrumentation
        if MLFLOW_AVAILABLE and mlflow is not None:
            with mlflow.start_run(run_name="ground_criterion"):
                mlflow.log_param("criterion_text", criterion_text)
                mlflow.log_param("criterion_type", criterion_type)

                start_time = time.time()
                result = await _safe_invoke()
                try:
                    duration = time.time() - start_time
                    mlflow.log_metric("latency_seconds", duration)

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
