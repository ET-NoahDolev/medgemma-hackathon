"""LangGraph ReAct agent for grounding clinical trial criteria."""

import logging
import os
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

try:
    from langchain_core.tools import tool  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    # Minimal fallback so this module can be imported without LangChain installed.
    def _tool(func=None, **_kwargs):  # type: ignore[no-redef]
        if func is None:
            return lambda f: f
        return func

    tool = _tool  # type: ignore[assignment]

try:
    from langchain_huggingface import (  # type: ignore[import-not-found]
        ChatHuggingFace,
        HuggingFacePipeline,
    )
except ImportError:  # pragma: no cover
    ChatHuggingFace = Any  # type: ignore[assignment]
    HuggingFacePipeline = Any  # type: ignore[assignment]

try:
    from langgraph.prebuilt import create_react_agent  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    def _create_react_agent(*_args: Any, **_kwargs: Any) -> Any:  # type: ignore[no-redef]
        raise ImportError(
            "LangGraph is required for GroundingAgent. Install grounding-service "
            "ML dependencies to enable AI grounding."
        )

    create_react_agent = _create_react_agent  # type: ignore[assignment]

from shared.field_schema import SEMANTIC_TYPE_MAPPING

from grounding_service.schemas import GroundingResult
from grounding_service.umls_client import UmlsClient

# Try to import mlflow (optional dependency for dev/observability)
try:
    import mlflow
    MLFLOW_AVAILABLE = True
    # database backend (SQLite)
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
        self.model_path = model_path or os.getenv(
            "MEDGEMMA_MODEL_PATH", "google/medgemma-1.5-4b-it"
        )
        self.quantization = quantization or os.getenv("MEDGEMMA_QUANTIZATION", "4bit")

        # Setup Jinja2 environment
        prompts_dir = Path(__file__).parent / "prompts"
        self.jinja_env = Environment(loader=FileSystemLoader(str(prompts_dir)))

        # Lazy-load the model (keeps tests lightweight if ML deps aren't installed)
        self.model: Any | None = None
        self.agent = None

    def _load_model(self) -> Any:
        """Load MedGemma model with appropriate quantization."""
        try:
            import torch  # type: ignore[import-not-found]
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "Torch is required to load MedGemma. Install grounding-service ML "
                "dependencies to enable AI grounding."
            ) from e

        if HuggingFacePipeline is Any or ChatHuggingFace is Any:  # type: ignore[comparison-overlap]
            raise ImportError(
                "LangChain HuggingFace integration is required to load MedGemma. "
                "Install grounding-service ML dependencies to enable AI grounding."
            )

        from transformers import BitsAndBytesConfig  # type: ignore[import-not-found]

        model_kwargs: dict[str, Any] = {
            "device_map": "auto",
            "torch_dtype": torch.bfloat16,
        }

        if self.quantization == "4bit":
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
            )
            model_kwargs["quantization_config"] = bnb_config
        elif self.quantization == "8bit":
            bnb_config = BitsAndBytesConfig(load_in_8bit=True)
            model_kwargs["quantization_config"] = bnb_config

        try:
            llm = HuggingFacePipeline.from_model_id(
                model_id=self.model_path,
                task="text-generation",
                model_kwargs=model_kwargs,
                pipeline_kwargs={"max_new_tokens": 512},
            )
            return ChatHuggingFace(llm=llm)
        except Exception as e:
            logger.error("Error loading model: %s", e)
            raise

    def _get_model(self) -> Any:
        """Get or lazily load the underlying model."""
        if self.model is None:
            self.model = self._load_model()
        return self.model

    def _get_agent(self) -> Any:
        """Get or create the ReAct agent."""
        if self.agent is None:
            tools = [search_concepts_tool, get_semantic_type_tool]
            self.agent = create_react_agent(
                model=self._get_model(),
                tools=tools,
                response_format=GroundingResult,
            )
        return self.agent

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
        # Build prompts from Jinja2 templates
        system_template = self.jinja_env.get_template("grounding_system.j2")
        user_template = self.jinja_env.get_template("grounding_user.j2")

        system_prompt = system_template.render(
            semantic_mappings=SEMANTIC_TYPE_MAPPING
        )
        user_prompt = user_template.render(
            criterion_text=criterion_text, criterion_type=criterion_type
        )

        # Get agent and invoke
        # Get agent and invoke
        agent = self._get_agent()
        
        # MLflow instrumentation
        if MLFLOW_AVAILABLE:
            with mlflow.start_run(run_name="ground_criterion"):
                mlflow.log_param("criterion_text", criterion_text)
                mlflow.log_param("criterion_type", criterion_type)
                mlflow.log_text(system_prompt, "prompt_system.txt")
                mlflow.log_text(user_prompt, "prompt_user.txt")
                
                start_time = logging.time.time()
                try:
                    result = await agent.ainvoke(
                        {
                            "messages": [
                                ("system", system_prompt),
                                ("user", user_prompt),
                            ]
                        }
                    )
                    duration = logging.time.time() - start_time
                    mlflow.log_metric("latency_seconds", duration)
                    
                    # Log raw result if serializable, or string representation
                    mlflow.log_text(str(result), "agent_result_raw.txt")
                except Exception as e:
                    mlflow.log_param("error", str(e))
                    raise e
        else:
            # Standard execution without tracking
            result = await agent.ainvoke(
                {
                    "messages": [
                        ("system", system_prompt),
                        ("user", user_prompt),
                    ]
                }
            )

        # Extract structured response
        if "structured_response" in result:
            return result["structured_response"]
        elif isinstance(result, dict) and "messages" in result:
            # Fallback: try to parse from last message
            messages = result["messages"]
            if messages:
                last_msg = messages[-1]
                if hasattr(last_msg, "content"):
                    # Try to parse JSON from content
                    import json

                    try:
                        content = last_msg.content
                        if isinstance(content, str):
                            # Look for JSON in the content
                            if "{" in content and "}" in content:
                                # Extract JSON portion
                                start = content.find("{")
                                end = content.rfind("}") + 1
                                json_str = content[start:end]
                                data = json.loads(json_str)
                                return GroundingResult(**data)
                    except Exception as e:
                        logger.warning("Failed to parse structured response: %s", e)

        # Final fallback: return empty result
        logger.warning("Could not extract structured response, returning empty")
        return GroundingResult(
            snomed_codes=[],
            field_mappings=[],
            reasoning="Agent execution completed but structured output not available",
        )


# Singleton instance
_agent_instance: GroundingAgent | None = None


def get_grounding_agent() -> GroundingAgent:
    """Get or create singleton grounding agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GroundingAgent()
    return _agent_instance
