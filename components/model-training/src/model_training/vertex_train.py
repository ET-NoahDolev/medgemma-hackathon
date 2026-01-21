"""Vertex AI fine-tuning helpers.

This module provides a thin wrapper for launching a managed LoRA/adapter tuning job
on Vertex AI using the Python SDK. It intentionally keeps dependencies imported
inside functions so that importing `model_training` stays lightweight in contexts
that only need local training.
"""

from __future__ import annotations

import os
from typing import Any


def train_vertex_lora(
    *,
    train_dataset_gcs: str,
    validation_dataset_gcs: str,
    output_uri: str,
    base_model: str = "google/medgemma-4b-it",
    epochs: int = 3,
    learning_rate: float = 2e-4,
    project_id: str | None = None,
    region: str | None = None,
) -> str:
    """Launch a LoRA (PEFT adapter) tuning job on Vertex AI.

    Args:
        train_dataset_gcs: GCS URI to the training JSONL, e.g.
            `gs://my-bucket/training/train_data.jsonl`.
        validation_dataset_gcs: GCS URI to the validation JSONL, e.g.
            `gs://my-bucket/training/eval_data.jsonl`.
        output_uri: GCS URI prefix for outputs, e.g.
            `gs://my-bucket/tuned-models/medgemma-lora-v1/`.
        base_model: Base model ID in Vertex Model Garden.
        epochs: Number of epochs.
        learning_rate: Learning rate.
        project_id: GCP project ID. Defaults to `GCP_PROJECT_ID` env var.
        region: GCP region. Defaults to `GCP_REGION` env var or `europe-west4`.

    Returns:
        Vertex tuning job resource name.

    Raises:
        ValueError: If required configuration or URIs are missing.
        ImportError: If Vertex AI SDK is not installed.

    Examples:
        >>> # doctest: +SKIP
        >>> train_vertex_lora(
        ...     train_dataset_gcs="gs://my-bucket/training/train.jsonl",
        ...     validation_dataset_gcs="gs://my-bucket/training/eval.jsonl",
        ...     output_uri="gs://my-bucket/tuned-models/medgemma-lora-v1/",
        ... )
    """
    if not train_dataset_gcs.strip():
        raise ValueError("train_dataset_gcs is required")
    if not validation_dataset_gcs.strip():
        raise ValueError("validation_dataset_gcs is required")
    if not output_uri.strip():
        raise ValueError("output_uri is required")

    resolved_project = (project_id or os.getenv("GCP_PROJECT_ID") or "").strip()
    resolved_region = (region or os.getenv("GCP_REGION") or "europe-west4").strip()
    if not resolved_project:
        raise ValueError("GCP_PROJECT_ID is required to submit a Vertex tuning job")
    if not resolved_region:
        raise ValueError("GCP_REGION is required to submit a Vertex tuning job")

    try:
        import vertexai  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Vertex tuning requires google-cloud-aiplatform installed."
        ) from exc

    try:
        from vertexai.tuning import sft, SourceModel  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Vertex tuning requires a recent google-cloud-aiplatform with "
            "`vertexai.tuning` support."
        ) from exc

    vertexai.init(project=resolved_project, location=resolved_region)

    job: Any = sft.train(
        source_model=SourceModel(base_model=base_model),
        tuning_mode="PEFT_ADAPTER",
        epochs=epochs,
        train_dataset=train_dataset_gcs,
        validation_dataset=validation_dataset_gcs,
        output_uri=output_uri,
        learning_rate=learning_rate,
    )

    resource_name = getattr(job, "resource_name", None)
    if not isinstance(resource_name, str) or not resource_name.strip():
        raise RuntimeError("Vertex tuning job did not return a resource_name")
    return resource_name

