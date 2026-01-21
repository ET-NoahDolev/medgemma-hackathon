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
        model_path: HuggingFace model ID or local path.
        quantization: Quantization level ("4bit", "8bit", or "none").
        max_new_tokens: Maximum tokens generated for a single call.
    """

    model_path: str = "google/medgemma-4b-it"
    quantization: str = "4bit"
    max_new_tokens: int = 512

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create AgentConfig from environment variables."""
        raw_max_tokens = os.getenv("MEDGEMMA_MAX_TOKENS", "512")
        try:
            max_tokens = int(raw_max_tokens)
        except ValueError:
            max_tokens = 512
        if max_tokens <= 0:
            max_tokens = 512
        return cls(
            model_path=os.getenv("MEDGEMMA_MODEL_PATH", cls.model_path),
            quantization=os.getenv("MEDGEMMA_QUANTIZATION", cls.quantization),
            max_new_tokens=max_tokens,
        )

