"""Configuration for MedGemma-based agents.

This module is shared across services to keep env var semantics consistent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for MedGemma agent infrastructure.

    Attributes:
        backend: Model backend selection ("local" or "vertex").
        model_path: HuggingFace model ID or local path.
        quantization: Quantization level ("4bit", "8bit", or "none").
        max_new_tokens: Maximum tokens generated for a single call.
        gcp_project_id: GCP project ID (required for Vertex backend).
        gcp_region: GCP region (required for Vertex backend).
        vertex_endpoint_id: Vertex AI endpoint ID (required for Vertex backend).
    """

    backend: str = "local"
    model_path: str = "google/medgemma-4b-it"
    quantization: str = "4bit"
    max_new_tokens: int = 512
    gcp_project_id: str = ""
    gcp_region: str = "europe-west4"
    vertex_endpoint_id: str = ""

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create AgentConfig from environment variables."""
        raw_backend = (
            os.getenv("MODEL_BACKEND") or os.getenv("MEDGEMMA_BACKEND") or "local"
        ).strip()
        backend = raw_backend.lower()
        if backend not in {"local", "vertex"}:
            backend = "local"

        raw_max_tokens = os.getenv("MEDGEMMA_MAX_TOKENS", "512")
        try:
            max_tokens = int(raw_max_tokens)
        except ValueError:
            max_tokens = 512
        if max_tokens <= 0:
            max_tokens = 512
        return cls(
            backend=backend,
            model_path=os.getenv("MEDGEMMA_MODEL_PATH", cls.model_path),
            quantization=os.getenv("MEDGEMMA_QUANTIZATION", cls.quantization),
            max_new_tokens=max_tokens,
            gcp_project_id=os.getenv("GCP_PROJECT_ID", cls.gcp_project_id),
            gcp_region=os.getenv("GCP_REGION", cls.gcp_region),
            vertex_endpoint_id=os.getenv("VERTEX_ENDPOINT_ID", cls.vertex_endpoint_id),
        )

