"""LangGraph ReAct agent for grounding clinical trial criteria."""

import logging
import os
from pathlib import Path
from typing import Any

import torch
from jinja2 import Environment, FileSystemLoader
from langchain_core.tools import tool
from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline
from langgraph.prebuilt import create_react_agent
from shared.field_schema import SEMANTIC_TYPE_MAPPING

from grounding_service.schemas import GroundingResult
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

        # Load model
        self.model = self._load_model()
        self.agent = None

    def _load_model(self) -> ChatHuggingFace:
        """Load MedGemma model with appropriate quantization."""
        from transformers import BitsAndBytesConfig

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

    def _get_agent(self) -> Any:
        """Get or create the ReAct agent."""
        if self.agent is None:
            tools = [search_concepts_tool, get_semantic_type_tool]
            self.agent = create_react_agent(
                model=self.model,
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
        agent = self._get_agent()
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
