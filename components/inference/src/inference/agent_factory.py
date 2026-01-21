"""Factory for creating LangGraph ReAct agents with Jinja2 prompts."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, TypeVar

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel

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


def _parse_structured_response(
    result: object,
    response_schema: type[TModel],
) -> TModel | None:
    """Parse a LangGraph result into a structured response if possible."""
    if isinstance(result, dict) and "structured_response" in result:
        structured = result["structured_response"]
        if isinstance(structured, response_schema):
            return structured
        if isinstance(structured, dict):
            return response_schema(**structured)

    if isinstance(result, dict) and "messages" in result:
        messages = result.get("messages")
        if isinstance(messages, list) and messages:
            last_msg = messages[-1]
            content = getattr(last_msg, "content", None)
            if isinstance(content, str):
                try:
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        return response_schema(**json.loads(content[start:end]))
                except (json.JSONDecodeError, TypeError, ValueError):
                    logger.warning("Failed to parse structured response from content")
    return None


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
    cache: list[Any] = []

    def _get_agent() -> Any:
        if cache:
            return cache[0]
        lg_create = _load_langgraph_create_react_agent()
        agent = lg_create(
            model=model_loader(),
            tools=tools,
            response_format=response_schema,
        )
        cache.append(agent)
        return agent

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

        parsed = _parse_structured_response(result, response_schema)
        if parsed is not None:
            return parsed

        logger.warning("No structured response available; returning default schema")
        return response_schema()

    return invoke

