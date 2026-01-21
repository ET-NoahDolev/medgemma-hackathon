"""Google Cloud Storage upload helpers for Vertex training datasets."""

from __future__ import annotations

import os
from pathlib import Path


def _normalize_bucket(bucket: str) -> str:
    raw = bucket.strip()
    if raw.startswith("gs://"):
        raw = raw[len("gs://") :]
    return raw.strip().strip("/")


def upload_training_data_to_gcs(
    *,
    local_path: str,
    gcs_bucket: str,
    gcs_path: str,
    project_id: str | None = None,
) -> str:
    """Upload a local file (e.g., JSONL) to Google Cloud Storage.

    This helper is intended for preparing training/validation JSONL files for
    Vertex managed tuning jobs.

    Args:
        local_path: Path to local file to upload.
        gcs_bucket: Bucket name or URI (e.g., `my-bucket` or `gs://my-bucket`).
        gcs_path: Object path within the bucket (e.g., `training/train.jsonl`).
        project_id: Optional GCP project ID. Defaults to `GCP_PROJECT_ID`.

    Returns:
        The resulting `gs://` URI for the uploaded object.

    Raises:
        ValueError: If required inputs are missing.
        FileNotFoundError: If the local file does not exist.
        ImportError: If google-cloud-storage is not installed.

    Examples:
        >>> # doctest: +SKIP
        >>> upload_training_data_to_gcs(
        ...     local_path="train.jsonl",
        ...     gcs_bucket="gs://my-bucket",
        ...     gcs_path="training/train.jsonl",
        ... )
        'gs://my-bucket/training/train.jsonl'
    """
    if not local_path.strip():
        raise ValueError("local_path is required")
    if not gcs_bucket.strip():
        raise ValueError("gcs_bucket is required")
    if not gcs_path.strip():
        raise ValueError("gcs_path is required")

    src = Path(local_path)
    if not src.exists():
        raise FileNotFoundError(str(src))

    bucket_name = _normalize_bucket(gcs_bucket)
    object_name = gcs_path.strip().lstrip("/")
    resolved_project = (project_id or os.getenv("GCP_PROJECT_ID") or "").strip() or None

    try:
        from google.cloud import storage  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Uploading to GCS requires google-cloud-storage installed."
        ) from exc

    client = storage.Client(project=resolved_project)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    blob.upload_from_filename(str(src))
    return f"gs://{bucket_name}/{object_name}"

