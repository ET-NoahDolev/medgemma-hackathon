"""Centralized MLflow tracing configuration.

This module provides configuration for MLflow tracing, including async logging,
sampling, and other production settings.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def configure_mlflow_tracing() -> None:
    """Configure MLflow tracing with production-ready settings.

    This function should be called once at application startup to configure
    MLflow tracing behavior. It sets up:
    - Async logging for production (non-blocking)
    - Sampling ratio if configured
    - Other tracing settings
    """
    try:
        import mlflow
    except ImportError:
        logger.debug("MLflow not available, skipping tracing configuration")
        return

    try:
        # Enable async logging for production (non-blocking trace logging)
        # This ensures trace logging doesn't impact request latency
        async_enabled = os.getenv("MLFLOW_TRACING_ASYNC", "true").lower() == "true"
        if async_enabled:
            try:
                # MLflow 3.8+ supports async tracing
                if hasattr(mlflow.tracing, "set_async"):
                    mlflow.tracing.set_async(True)
                    logger.info("MLflow async tracing enabled")
                else:
                    logger.debug("MLflow async tracing not available in this version")
            except Exception as e:
                logger.warning("Failed to enable async tracing: %s", e)

        # Configure sampling ratio if specified (for high-throughput scenarios)
        sampling_ratio_str = os.getenv("MLFLOW_TRACING_SAMPLING_RATIO")
        if sampling_ratio_str:
            try:
                sampling_ratio = float(sampling_ratio_str)
                if 0.0 <= sampling_ratio <= 1.0:
                    if hasattr(mlflow.tracing, "set_sampling_ratio"):
                        mlflow.tracing.set_sampling_ratio(sampling_ratio)
                        logger.info(
                            f"MLflow tracing sampling ratio set to {sampling_ratio}"
                        )
                    else:
                        logger.debug(
                            "MLflow tracing sampling not available in this version"
                        )
                else:
                    logger.warning(
                        f"Invalid sampling ratio {sampling_ratio}, "
                        "must be between 0.0 and 1.0"
                    )
            except ValueError:
                logger.warning(
                    f"Invalid MLFLOW_TRACING_SAMPLING_RATIO value: {sampling_ratio_str}"
                )

    except Exception as e:
        logger.warning("Failed to configure MLflow tracing: %s", e, exc_info=True)


def get_trace_context() -> dict[str, Any]:
    """Get current trace context for adding custom metadata.

    Returns:
        Dictionary with trace context information that can be used
        to add metadata to traces.
    """
    try:
        import mlflow

        # Get active trace if available
        # Type ignore because MLflow tracing API may not be in type stubs
        active_trace = mlflow.tracing.get_active_trace()  # type: ignore[attr-defined]
        if active_trace:
            span_id = (
                active_trace.span_id
                if hasattr(active_trace, "span_id")
                else None
            )
            return {
                "trace_id": active_trace.trace_id,
                "span_id": span_id,
            }
    except (ImportError, AttributeError):
        pass

    return {}


def set_trace_tags(tags: dict[str, str]) -> None:
    """Set tags on the active trace.

    Args:
        tags: Dictionary of tag key-value pairs to add to the trace.
    """
    try:
        import mlflow

        # Type ignore because MLflow tracing API may not be in type stubs
        active_trace = mlflow.tracing.get_active_trace()  # type: ignore[attr-defined]
        if active_trace:
            for key, value in tags.items():
                # Type ignore because MLflow tracing API may not be in type stubs
                mlflow.tracing.set_tag(key, value)  # type: ignore[attr-defined]
    except (ImportError, AttributeError) as e:
        logger.debug("Failed to set trace tags: %s", e)
