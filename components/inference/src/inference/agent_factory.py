"""Factory for creating LangGraph ReAct agents with Jinja2 prompts."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, TypeVar

from dotenv import find_dotenv
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel

logger = logging.getLogger(__name__)


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


# Configure MLflow tracking URI at module level to avoid filesystem backend warning
# Set environment variable before import so MLflow reads it during initialization
_mlflow_uri = _get_mlflow_tracking_uri()
os.environ.setdefault("MLFLOW_TRACKING_URI", _mlflow_uri)

# Optional MLflow support for logging prompts and responses
_MLFLOW_AVAILABLE = False
try:
    import mlflow

    mlflow.set_tracking_uri(_mlflow_uri)
    # Don't set experiment here - let the calling service set it
    # This allows nested runs to work correctly
    _MLFLOW_AVAILABLE = True
except ImportError:
    pass
except Exception as e:
    logger.warning("Failed to initialize MLflow in agent_factory: %s", e, exc_info=True)

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

        # MLflow logging for prompts and responses (optional)
        should_end_run = False
        if _MLFLOW_AVAILABLE:
            try:
                # Ensure tracking URI is set (in case it was changed)
                mlflow.set_tracking_uri(_mlflow_uri)
                
                # Check if we're already in an MLflow run (started by calling service)
                active_run = mlflow.active_run()
                if active_run is None:
                    # Start a new run if none exists (not nested since no parent)
                    # Use a default experiment if none is set
                    try:
                        mlflow.set_experiment("medgemma-inference")
                    except Exception:
                        pass  # Experiment will be created automatically
                    mlflow.start_run(run_name="agent_invoke")
                    should_end_run = True
                else:
                    # Start a nested run if parent exists
                    mlflow.start_run(run_name="agent_invoke", nested=True)
                    should_end_run = True

                # Log prompts
                mlflow.log_text(system_prompt, artifact_file="system_prompt.txt")
                mlflow.log_text(user_prompt, artifact_file="user_prompt.txt")
                mlflow.log_params({
                    "system_template": system_template,
                    "user_template": user_template,
                })
                logger.debug("MLflow: Logged prompts for agent invocation")
            except Exception as e:
                logger.warning("MLflow prompt logging failed (non-fatal): %s", e, exc_info=True)
                should_end_run = False

        result = await agent.ainvoke(
            {
                "messages": [
                    ("system", system_prompt),
                    ("user", user_prompt),
                ]
            }
        )

        parsed = _parse_structured_response(result, response_schema)

        # Log response if MLflow is available
        if _MLFLOW_AVAILABLE:
            try:
                if parsed is not None:
                    # Log the structured response as JSON
                    response_json = parsed.model_dump_json(indent=2)
                    mlflow.log_text(response_json, artifact_file="response.json")
                    logger.debug("MLflow: Logged structured response")

                # Also log the raw result if available
                if isinstance(result, dict):
                    result_str = json.dumps(result, indent=2, default=str)
                    mlflow.log_text(result_str, artifact_file="raw_result.json")
                    logger.debug("MLflow: Logged raw result")

                if should_end_run:
                    mlflow.end_run()
                    logger.debug("MLflow: Ended agent invocation run")
            except Exception as e:
                logger.warning("MLflow response logging failed (non-fatal): %s", e, exc_info=True)
                if should_end_run:
                    try:
                        mlflow.end_run()
                    except Exception as end_error:
                        logger.warning("Failed to end MLflow run: %s", end_error)

        if parsed is not None:
            return parsed

        logger.warning("No structured response available; returning default schema")
        return response_schema()

    return invoke

