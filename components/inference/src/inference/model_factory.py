"""Factory for creating MedGemma model loaders.

The factory returns a lazy loader (callable). Importing this module should remain
lightweight; heavyweight ML dependencies are imported only when the loader runs.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from inference.config import AgentConfig


def _ensure_hf_auth_env() -> None:
    hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
    if not hf_token:
        return

    os.environ["HF_TOKEN"] = hf_token
    os.environ["HUGGINGFACEHUB_API_TOKEN"] = hf_token
    try:
        from huggingface_hub import login

        login(token=hf_token, add_to_git_credential=False)
    except (ImportError, OSError, RuntimeError, ValueError):
        # Token is already set in env vars; continue.
        return


def _import_torch() -> Any:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Torch is required to load MedGemma. Install inference ML dependencies."
        ) from exc
    return torch


def _import_langchain_hf() -> tuple[Any, Any]:
    try:
        from langchain_huggingface import (
            ChatHuggingFace,
            HuggingFacePipeline,
        )
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "langchain-huggingface is required to load MedGemma. "
            "Install inference ML dependencies."
        ) from exc
    return ChatHuggingFace, HuggingFacePipeline


def _is_model_cached(model_path: str) -> bool:
    try:
        from huggingface_hub import (
            try_to_load_from_cache,
        )

        config_path = try_to_load_from_cache(
            repo_id=model_path, filename="config.json", revision="main"
        )
        return config_path is not None
    except (ImportError, OSError, RuntimeError, ValueError):
        return False


def _build_model_kwargs(*, quantization: str, torch: Any) -> dict[str, Any]:
    from transformers import BitsAndBytesConfig

    model_kwargs: dict[str, Any] = {"device_map": "auto", "dtype": torch.bfloat16}

    quant = (quantization or "none").lower()
    if quant == "4bit":
        model_kwargs["quantization_config"] = BitsAndBytesConfig(  # type: ignore[no-untyped-call]
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
        )
    elif quant == "8bit":
        model_kwargs["quantization_config"] = BitsAndBytesConfig(  # type: ignore[no-untyped-call]
            load_in_8bit=True
        )
    elif quant == "none":
        pass
    else:
        raise ValueError(f"Unsupported quantization: {quantization}")
    return model_kwargs


def _load_hf_pipeline(
    *,
    model_id: str,
    max_new_tokens: int,
    hf_pipeline_cls: Any,
    model_kwargs: dict[str, Any],
    model_cached: bool,
) -> Any:
    pipeline_kwargs: dict[str, Any] = {"max_new_tokens": max_new_tokens}
    if model_cached:
        extra_kwargs: dict[str, Any] = {"local_files_only": True}
    else:
        extra_kwargs = {}

    try:
        return hf_pipeline_cls.from_model_id(
            model_id=model_id,
            task="text-generation",
            model_kwargs=model_kwargs,
            pipeline_kwargs=pipeline_kwargs,
            **extra_kwargs,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        lowered = str(exc).lower()
        if model_cached and ("local_files_only" in lowered or "not found" in lowered):
            extra_kwargs.pop("local_files_only", None)
            return hf_pipeline_cls.from_model_id(
                model_id=model_id,
                task="text-generation",
                model_kwargs=model_kwargs,
                pipeline_kwargs=pipeline_kwargs,
                **extra_kwargs,
            )
        raise


def create_model_loader(config: AgentConfig | None = None) -> Callable[[], Any]:
    """Create a lazy MedGemma model loader for the configured backend.

    Args:
        config: Agent configuration. Defaults to `AgentConfig.from_env()`.

    Returns:
        Callable that loads and returns a LangChain chat model when invoked.
    """
    cfg = config or AgentConfig.from_env()
    if cfg.backend == "vertex":
        return _create_vertex_model_loader(cfg)
    return _create_local_model_loader(cfg)


def _create_vertex_model_loader(cfg: AgentConfig) -> Callable[[], Any]:
    """Create a lazy Vertex AI endpoint model loader.

    This loader expects Application Default Credentials (ADC) to be available
    (e.g., via `gcloud auth application-default login`).

    Raises:
        ValueError: If required Vertex configuration is missing.
        ImportError: If Vertex dependencies are not installed.
    """
    project_id = (cfg.gcp_project_id or "").strip()
    region = (cfg.gcp_region or "").strip()
    endpoint_id = (cfg.vertex_endpoint_id or "").strip()

    if not project_id:
        raise ValueError("GCP_PROJECT_ID is required when MODEL_BACKEND=vertex")
    if not region:
        raise ValueError("GCP_REGION is required when MODEL_BACKEND=vertex")
    if not endpoint_id:
        raise ValueError("VERTEX_ENDPOINT_ID is required when MODEL_BACKEND=vertex")

    cache: list[Any] = []

    def load_model() -> Any:
        if cache:
            return cache[0]

        try:
            import vertexai
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "Vertex AI backend requires google-cloud-aiplatform installed."
            ) from exc

        try:
            from langchain_google_vertexai import ChatVertexAI
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "Vertex AI backend requires langchain-google-vertexai installed."
            ) from exc

        vertexai.init(project=project_id, location=region)
        endpoint_resource_name = (
            f"projects/{project_id}/locations/{region}/endpoints/{endpoint_id}"
        )

        # Note: model_path/quantization are ignored for Vertex endpoints.
        model = ChatVertexAI(
            model_name=endpoint_resource_name,
            max_output_tokens=cfg.max_new_tokens,
        )

        cache.append(model)
        return model

    return load_model


def _create_local_model_loader(cfg: AgentConfig) -> Callable[[], Any]:
    """Create a lazy local HuggingFace pipeline model loader."""
    cache: list[Any] = []

    def load_model() -> Any:
        if cache:
            return cache[0]

        _ensure_hf_auth_env()
        torch = _import_torch()
        chat_hf_cls, hf_pipeline_cls = _import_langchain_hf()
        model_cached = _is_model_cached(cfg.model_path)
        model_kwargs = _build_model_kwargs(quantization=cfg.quantization, torch=torch)

        llm = _load_hf_pipeline(
            model_id=cfg.model_path,
            max_new_tokens=cfg.max_new_tokens,
            hf_pipeline_cls=hf_pipeline_cls,
            model_kwargs=model_kwargs,
            model_cached=model_cached,
        )

        model = chat_hf_cls(llm=llm)
        cache.append(model)
        return model

    return load_model

