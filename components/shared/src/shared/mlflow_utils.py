from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import find_dotenv

logger = logging.getLogger(__name__)


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
        experiment_name: The MLflow experiment name to use.
    """
    try:
        import mlflow
    except ImportError:
        logger.warning("MLflow not installed; running without tracing")
        return

    try:
        uri = get_mlflow_tracking_uri()
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(experiment_name)

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
            experiment_name,
            run_tracer_inline,
        )
    except Exception as exc:  # noqa: BLE001 - surface config issues without crashing
        logger.warning("MLflow configuration failed: %s", exc)
