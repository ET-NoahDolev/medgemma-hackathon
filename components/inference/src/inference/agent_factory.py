"""Factory for creating LangGraph ReAct agents with Jinja2 prompts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, TypeVar

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from shared.lazy_cache import lazy_singleton

logger = logging.getLogger(__name__)


TModel = TypeVar("TModel", bound=BaseModel)


def _load_langgraph_create_react_agent() -> Any:
    """Load LangGraph's prebuilt create_react_agent lazily."""
    try:
        from langgraph.prebuilt import create_react_agent as lg_create_react_agent
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "langgraph is required to create ReAct agents. "
            "Install inference ML dependencies."
        ) from exc
    return lg_create_react_agent


def create_react_agent(
    *,
    model_loader: Callable[[], Any],
    prompts_dir: Path,
    tools: list[Any],
    response_schema: type[TModel],
    system_template: str,
    user_template: str,
) -> Callable[[Mapping[str, Any]], Awaitable[TModel]]:
    """Create a reusable ReAct agent invocation function.

    This function composes:
    - lazy model loading (shared across services)
    - Jinja2 prompt rendering (service-specific templates)
    - LangGraph ReAct agent execution with structured output

    Args:
        model_loader: Callable returning a LangChain-compatible chat model.
        prompts_dir: Directory containing Jinja2 templates.
        tools: Tools exposed to the ReAct agent.
        response_schema: Pydantic model for structured output.
        system_template: Filename of the system prompt template.
        user_template: Filename of the user prompt template.

    Returns:
        Async function that takes prompt variables and returns a structured response.
    """
    jinja_env = Environment(loader=FileSystemLoader(str(prompts_dir)))

    @lazy_singleton
    def _get_agent() -> Any:
        lg_create = _load_langgraph_create_react_agent()
        model = model_loader()
        return lg_create(
            model=model,
            tools=tools,
            response_format=response_schema,
        )

    async def invoke(prompt_vars: Mapping[str, Any]) -> TModel:
        system_tpl = jinja_env.get_template(system_template)
        user_tpl = jinja_env.get_template(user_template)

        system_prompt = system_tpl.render(**prompt_vars)
        user_prompt = user_tpl.render(**prompt_vars)

        agent = _get_agent()

        result = await agent.ainvoke(
            {
                "messages": [
                    ("system", system_prompt),
                    ("user", user_prompt),
                ]
            }
        )
        structured = None
        if isinstance(result, dict):
            structured = result.get("structured_response")

        if isinstance(structured, response_schema):
            return structured
        if isinstance(structured, dict):
            return response_schema(**structured)

        raise ValueError(
            "Model did not return structured output. Ensure the model supports "
            "response_format (Gemini, GPT-4o, etc.) and prompts are compatible."
        )

    return invoke

