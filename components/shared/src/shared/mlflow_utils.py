from __future__ import annotations

import contextvars
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from dotenv import find_dotenv

logger = logging.getLogger(__name__)

# Context variable to store trace metadata that should be applied when trace is created
_trace_metadata_ctx: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar(
    "mlflow_trace_metadata", default={}
)

T = TypeVar("T")


def get_mlflow_tracking_uri() -> str:
    """Return the MLflow tracking URI for the repository.

    Raises:
        RuntimeError: If a .env file cannot be found to infer repo root.
    """
    env_path = find_dotenv()
    if not env_path:
        raise RuntimeError("Cannot determine repo root: .env file not found.")
    repo_root = Path(env_path).parent.absolute()
    db_path = repo_root / "mlflow.db"
    return f"sqlite:///{db_path}"


def configure_mlflow_once(experiment_name: str) -> None:
    """Configure MLflow at application startup using autolog only.

    This function configures MLflow tracing for LangChain/LangGraph agents.
    For async operations (ainvoke), run_tracer_inline=True ensures proper
    context propagation and more immediate trace writes.

    Note: Traces are written incrementally, but the MLflow UI requires
    manual refresh to see traces as they're being created. Async tracing
    (MLFLOW_TRACING_ASYNC) may buffer writes for performance, which can
    delay trace visibility.

    Args:
        experiment_name: The MLflow experiment name to use. A UTC timestamp
            suffix is appended to separate runs by session.
    """
    try:
        import mlflow
    except ImportError:
        logger.warning("MLflow not installed; running without tracing")
        return

    try:
        uri = get_mlflow_tracking_uri()
        mlflow.set_tracking_uri(uri)
        experiment_name_with_timestamp = _format_experiment_name(experiment_name)
        mlflow.set_experiment(experiment_name_with_timestamp)

        # Enable run_tracer_inline for async operations (ainvoke) to ensure
        # proper context propagation. This makes the tracer run in the main
        # async task rather than a thread pool, which can improve trace
        # visibility for long-running async operations.
        run_tracer_inline_env = os.getenv("MLFLOW_RUN_TRACER_INLINE", "true")
        run_tracer_inline = run_tracer_inline_env.lower() == "true"

        mlflow.langchain.autolog(run_tracer_inline=run_tracer_inline)

        if hasattr(mlflow, "langgraph"):
            mlflow.langgraph.autolog()

        logger.info(
            "MLflow configured: uri=%s experiment=%s run_tracer_inline=%s",
            uri,
            experiment_name_with_timestamp,
            run_tracer_inline,
        )
    except Exception as exc:  # noqa: BLE001 - surface config issues without crashing
        logger.warning("MLflow configuration failed: %s", exc)


def _format_experiment_name(
    experiment_name: str, timestamp: datetime | None = None
) -> str:
    """Return an MLflow experiment name with a UTC timestamp suffix."""
    resolved_timestamp = timestamp or datetime.now(timezone.utc)
    suffix = resolved_timestamp.strftime("%Y%m%d-%H%M%S")
    return f"{experiment_name}-{suffix}"


def set_trace_metadata(
    user_id: str | None = None,
    session_id: str | None = None,
    run_id: str | None = None,
) -> None:
    """Set metadata on the current MLflow trace.

    Groups traces by user, session, and run. Should be called within the context
    where traces are being created (e.g., before agent invocations). The metadata
    keys `mlflow.trace.user`, `mlflow.trace.session`, and `run_id` are used by
    MLflow to group traces.

    With autologging, traces are created automatically when agents are invoked.
    This function:
    1. Stores metadata in a context variable for later use
    2. Tries to update the current trace if one exists
    3. The metadata will be applied when the trace is created by autologging

    Args:
        user_id: Optional user identifier to associate with the trace.
        session_id: Optional session identifier to group traces from the same
            session.
        run_id: Optional run identifier to group all traces from a single
            extraction run.

    Example:
        ```python
        set_trace_metadata(
            user_id="user-123", session_id="session-456", run_id="run-789"
        )
        # Agent invocations after this will have trace metadata set
        result = await agent.invoke(...)
        # After invocation, try to update trace metadata again
        set_trace_metadata(
            user_id="user-123", session_id="session-456", run_id="run-789"
        )
        ```
    """
    try:
        import mlflow
    except ImportError:
        logger.debug("MLflow not installed; skipping trace metadata update")
        return

    try:
        metadata: dict[str, str] = {}
        if user_id:
            metadata["mlflow.trace.user"] = user_id
        if session_id:
            metadata["mlflow.trace.session"] = session_id
        if run_id:
            metadata["run_id"] = run_id

        if not metadata:
            return

        # Store metadata in context variable for later use
        existing_metadata = _trace_metadata_ctx.get({})
        existing_metadata.update(metadata)
        _trace_metadata_ctx.set(existing_metadata)

        # Try to update the current trace if one exists
        try:
            mlflow.update_current_trace(metadata=metadata)
            logger.debug(
                "Updated trace metadata: user_id=%s session_id=%s run_id=%s",
                user_id,
                session_id,
                run_id,
            )
        except Exception:  # noqa: BLE001
            # No active trace yet - this is expected with autologging
            # The trace will be created when the agent is invoked
            # Metadata is stored in context and will be applied later
            logger.debug(
                "Trace not yet active (stored in context): "
                "user_id=%s session_id=%s run_id=%s",
                user_id,
                session_id,
                run_id,
            )
    except Exception as exc:  # noqa: BLE001 - surface issues without crashing
        logger.debug("Failed to set trace metadata: %s", exc)
