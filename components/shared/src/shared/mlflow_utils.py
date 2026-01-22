from __future__ import annotations

import logging
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

        mlflow.langchain.autolog()
        if hasattr(mlflow, "langgraph"):
            mlflow.langgraph.autolog()

        logger.info("MLflow configured: uri=%s experiment=%s", uri, experiment_name)
    except Exception as exc:  # noqa: BLE001 - surface config issues without crashing
        logger.warning("MLflow configuration failed: %s", exc)
