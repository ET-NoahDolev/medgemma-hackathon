"""Factory for creating LangGraph ReAct agents with Jinja2 prompts."""

from __future__ import annotations

import importlib.metadata
import json
import logging
import time
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
        recursion_limit: Maximum number of agentic steps before stopping (default: 10).

    Returns:
        Async function that takes prompt variables and returns a structured response.
    """
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
        system_prompt, user_prompt = render_prompts(
            prompts_dir=prompts_dir,
            system_template=system_template,
            user_template=user_template,
            prompt_vars=prompt_vars,
        )

        agent = _get_agent()

        # region agent log
        try:
            try:
                mlflow_version = importlib.metadata.version("mlflow")
            except importlib.metadata.PackageNotFoundError:
                mlflow_version = "unknown"
            try:
                langgraph_version = importlib.metadata.version("langgraph")
            except importlib.metadata.PackageNotFoundError:
                langgraph_version = "unknown"
            active_trace = None
            try:
                import mlflow  # type: ignore

                if hasattr(mlflow, "tracing") and hasattr(
                    mlflow.tracing, "get_active_trace"
                ):
                    active_trace = mlflow.tracing.get_active_trace()
            except Exception:
                active_trace = None
            with open(
                "/Users/noahdolevelixir/Code/gemma-hackathon/.cursor/debug.log",
                "a",
                encoding="utf-8",
            ) as log_file:
                log_file.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "trace-debug",
                            "hypothesisId": "H3",
                            "location": "agent_factory.py:120",
                            "message": "about to invoke agent",
                            "data": {
                                "agent_type": type(agent).__name__,
                                "has_ainvoke": hasattr(agent, "ainvoke"),
                                "mlflow_version": mlflow_version,
                                "langgraph_version": langgraph_version,
                                "active_trace_is_none": active_trace is None,
                                "active_trace_type": None
                                if active_trace is None
                                else type(active_trace).__name__,
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # endregion

        result = await agent.ainvoke(
            {
                "messages": [
                    ("system", system_prompt),
                    ("user", user_prompt),
                ]
            },
            config={"recursion_limit": recursion_limit},
        )
        # region agent log
        try:
            with open(
                "/Users/noahdolevelixir/Code/gemma-hackathon/.cursor/debug.log",
                "a",
                encoding="utf-8",
            ) as log_file:
                log_file.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "trace-debug",
                            "hypothesisId": "H4",
                            "location": "agent_factory.py:144",
                            "message": "agent invoke completed",
                            "data": {"result_type": type(result).__name__},
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # endregion
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

