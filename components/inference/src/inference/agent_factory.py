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


def render_prompts(
    *,
    prompts_dir: Path,
    system_template: str,
    user_template: str,
    prompt_vars: Mapping[str, Any],
) -> tuple[str, str]:
    """Render system and user prompts from Jinja templates."""
    jinja_env = Environment(loader=FileSystemLoader(str(prompts_dir)))
    system_tpl = jinja_env.get_template(system_template)
    user_tpl = jinja_env.get_template(user_template)
    return system_tpl.render(**prompt_vars), user_tpl.render(**prompt_vars)


def create_structured_extractor(
    *,
    model_loader: Callable[[], Any],
    prompts_dir: Path,
    response_schema: type[TModel],
    system_template: str,
    user_template: str,
) -> Callable[[Mapping[str, Any]], Awaitable[TModel]]:
    """Create a structured extraction function using model.with_structured_output().

    This function uses the model's native structured output support (e.g., Gemini's
    JSON schema mode) to return validated Pydantic instances directly. This is more
    reliable than relying on agent frameworks' structured output handling.

    Args:
        model_loader: Callable returning a LangChain-compatible chat model that
            supports with_structured_output().
        prompts_dir: Directory containing Jinja2 templates.
        response_schema: Pydantic model for structured output.
        system_template: Filename of the system prompt template.
        user_template: Filename of the user prompt template.

    Returns:
        Async function that takes prompt variables and returns a validated
        Pydantic instance.
    """
    @lazy_singleton
    def _get_structured_model() -> Any:
        model = model_loader()
        return model.with_structured_output(response_schema)

    async def invoke(prompt_vars: Mapping[str, Any]) -> TModel:
        system_prompt, user_prompt = render_prompts(
            prompts_dir=prompts_dir,
            system_template=system_template,
            user_template=user_template,
            prompt_vars=prompt_vars,
        )

        structured_model = _get_structured_model()
        result = await structured_model.ainvoke([
            ("system", system_prompt),
            ("user", user_prompt),
        ])

        # with_structured_output returns the Pydantic instance directly
        if isinstance(result, response_schema):
            return result
        if isinstance(result, dict):
            return response_schema(**result)

        raise ValueError(
            f"Model did not return structured output of type "
            f"{response_schema.__name__}. Got: {type(result)}"
        )

    return invoke


def _load_langgraph_create_react_agent() -> Any:
    """Load LangGraph's prebuilt create_react_agent lazily."""
    try:
        from langchain.agents import create_agent as lc_create_agent

        def lg_create_react_agent(
            *,
            model: Any,
            tools: list[Any],
            response_format: Any,
        ) -> Any:
            return lc_create_agent(
                model=model,
                tools=tools,
                response_format=response_format,
            )

    except ImportError:  # pragma: no cover
        try:
            from langgraph.prebuilt import create_react_agent as lg_create_react_agent
        except ImportError as fallback_exc:  # pragma: no cover
            raise ImportError(
                "langgraph or langchain agents are required to create ReAct agents. "
                "Install inference ML dependencies."
            ) from fallback_exc
    return lg_create_react_agent


def create_react_agent(
    *,
    model_loader: Callable[[], Any],
    prompts_dir: Path,
    tools: list[Any],
    response_schema: type[TModel],
    system_template: str,
    user_template: str,
    recursion_limit: int = 10,
) -> Callable[[Mapping[str, Any]], Awaitable[TModel]]:
    """Create a reusable ReAct agent invocation function with structured output.

    This function composes:
    - lazy model loading (shared across services)
    - Jinja2 prompt rendering (service-specific templates)
    - LangGraph ReAct agent execution for tool calling
    - Structured output extraction using model.with_structured_output()

    When tools are present, the agent executes tool calls, then uses
    with_structured_output() on the final message to extract structured results.

    Args:
        model_loader: Callable returning a LangChain-compatible chat model.
        prompts_dir: Directory containing Jinja2 templates.
        tools: Tools exposed to the ReAct agent.
        response_schema: Pydantic model for structured output.
        system_template: Filename of the system prompt template.
        user_template: Filename of the user prompt template.
        recursion_limit: Maximum number of agentic steps before stopping (default: 10).

    Returns:
        Async function that takes prompt variables and returns a structured response.
    """
    @lazy_singleton
    def _get_agent() -> Any:
        lg_create = _load_langgraph_create_react_agent()
        model = model_loader()
        # Don't use response_format - we'll handle structured output separately
        return lg_create(
            model=model,
            tools=tools,
            response_format=None,
        )

    @lazy_singleton
    def _get_structured_model() -> Any:
        model = model_loader()
        return model.with_structured_output(response_schema)

    async def invoke(prompt_vars: Mapping[str, Any]) -> TModel:
        system_prompt, user_prompt = render_prompts(
            prompts_dir=prompts_dir,
            system_template=system_template,
            user_template=user_template,
            prompt_vars=prompt_vars,
        )

        agent = _get_agent()

        # Run the agent to execute tool calls
        result = await agent.ainvoke(
            {
                "messages": [
                    ("system", system_prompt),
                    ("user", user_prompt),
                ]
            },
            config={"recursion_limit": recursion_limit},
        )

        # Extract messages from agent result
        messages = result.get("messages", []) if isinstance(result, dict) else []
        if not messages:
            raise ValueError("Agent returned no messages")

        # Convert agent messages to format expected by structured model
        # Include full conversation history (system, user, tool calls, tool responses)
        from langchain_core.messages import SystemMessage

        structured_messages = []
        if system_prompt:
            structured_messages.append(SystemMessage(content=system_prompt))

        # Add all messages from the agent (includes tool calls and responses)
        structured_messages.extend(messages)

        # Use with_structured_output to extract structured result from full conversation
        structured_model = _get_structured_model()
        structured_result = await structured_model.ainvoke(structured_messages)

        if isinstance(structured_result, response_schema):
            return structured_result
        if isinstance(structured_result, dict):
            return response_schema(**structured_result)

        raise ValueError(
            f"Model did not return structured output of type "
            f"{response_schema.__name__}. Got: {type(structured_result)}"
        )

    return invoke

