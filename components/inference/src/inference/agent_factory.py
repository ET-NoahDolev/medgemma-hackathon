"""Factory for creating LangGraph ReAct agents with Jinja2 prompts."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, TypeVar

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, ValidationError
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


def _count_tool_call_steps(messages: list[Any]) -> int:
    return sum(1 for message in messages if getattr(message, "tool_calls", None))


def _try_parse_last_message(
    messages: list[Any], response_schema: type[TModel]
) -> TModel | None:
    last_ai_message = next(
        (message for message in reversed(messages) if message.type == "ai"),
        None,
    )
    if not last_ai_message or getattr(last_ai_message, "tool_calls", None):
        return None
    if not isinstance(last_ai_message.content, str):
        return None
    parsed = _try_parse_json_text(last_ai_message.content)
    if parsed is None:
        return None
    try:
        return response_schema(**parsed)
    except (ValidationError, TypeError):
        return None


def _try_parse_json_text(text: str) -> dict[str, Any] | None:
    trimmed = text.strip()
    if not trimmed:
        return None
    candidates = [trimmed]
    if "{" in trimmed and "}" in trimmed:
        start = trimmed.find("{")
        end = trimmed.rfind("}")
        if 0 <= start < end:
            candidates.append(trimmed[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _log_agent_metrics(tool_call_steps: int, recursion_limit: int) -> None:
    try:
        import mlflow
    except ImportError:
        return

    metadata = {
        "agent.tool_call_steps": str(tool_call_steps),
        "agent.recursion_limit": str(recursion_limit),
    }
    try:
        mlflow.update_current_trace(metadata=metadata)
    except (AttributeError, RuntimeError, ValueError):
        return


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

        if os.getenv("ENABLE_VERTEX_CACHE", "").lower() == "true":
            # #region agent log
            import time as _time
            try:
                _df = open("/Users/noahdolevelixir/Code/gemma-hackathon/.cursor/debug.log", "a")
                _df.write(
                    '{"location":"agent_factory.invoke:before_cache","message":"prompts after render","data":{"len_system":'
                    + str(len(system_prompt))
                    + ',"len_user":'
                    + str(len(user_prompt))
                    + ',"system_preview":"'
                    + system_prompt[:150].replace('"', '\\"').replace('\n', '\\n')
                    + '...","user_preview":"'
                    + user_prompt[:150].replace('"', '\\"').replace('\n', '\\n')
                    + '..."},"hypothesisId":"H6","timestamp":'
                    + str(int(_time.time() * 1000))
                    + '}\n'
                )
                _df.close()
            except Exception:
                pass
            # #endregion
            try:
                from inference.vertex_cache import get_vertex_cache

                cache = get_vertex_cache()
                response_text = cache.generate_with_cache(system_prompt, user_prompt)
                parsed = json.loads(response_text)
                return response_schema(**parsed)
            except (
                json.JSONDecodeError,
                ValidationError,
                TypeError,
                ValueError,
            ) as exc:
                logger.debug("Vertex cache parse failed, falling back: %s", exc)

        structured_model = _get_structured_model()
        result = await structured_model.ainvoke(
            [
                ("system", system_prompt),
                ("user", user_prompt),
            ]
        )

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

        tool_call_steps = _count_tool_call_steps(messages)
        if tool_call_steps >= max(1, recursion_limit // 2):
            logger.warning(
                "Agent nearing recursion limit: tool_call_steps=%s limit=%s",
                tool_call_steps,
                recursion_limit,
            )
        _log_agent_metrics(tool_call_steps, recursion_limit)

        parsed_direct = _try_parse_last_message(messages, response_schema)
        if parsed_direct is not None:
            return parsed_direct

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

