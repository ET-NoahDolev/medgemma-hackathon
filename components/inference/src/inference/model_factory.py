"""Factory for creating MedGemma model loaders.

The factory returns a lazy loader (callable). Importing this module should remain
lightweight; heavyweight ML dependencies are imported only when the loader runs.
"""

from __future__ import annotations

import os
from typing import Any, Callable
import json
import time

from inference.config import AgentConfig


def _debug_log(*, hypothesis_id: str, location: str, message: str, data: dict[str, Any]) -> None:
    """Write a debug log line for runtime diagnosis."""
    payload = {
        "sessionId": "debug-session",
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(
            "/Users/noahdolevelixir/Code/gemma-hackathon/.cursor/debug.log",
            "a",
            encoding="utf-8",
        ) as log_file:
            log_file.write(json.dumps(payload) + "\n")
    except OSError:
        return


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


def _validate_vertex_config(cfg: AgentConfig) -> tuple[str, str, str, str]:
    project_id = (cfg.gcp_project_id or "").strip()
    region = (cfg.gcp_region or "").strip()
    endpoint_id = (cfg.vertex_endpoint_id or "").strip()
    vertex_model_name = (cfg.vertex_model_name or "").strip()

    if not project_id:
        raise ValueError("GCP_PROJECT_ID is required when MODEL_BACKEND=vertex")
    if not region:
        raise ValueError("GCP_REGION is required when MODEL_BACKEND=vertex")
    if not endpoint_id and not vertex_model_name:
        raise ValueError(
            "VERTEX_ENDPOINT_ID or VERTEX_MODEL_NAME is required when "
            "MODEL_BACKEND=vertex"
        )

    return project_id, region, endpoint_id, vertex_model_name


def _build_vertex_genai_model(
    *, model_name: str, project_id: str, region: str, max_tokens: int
) -> Any:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Vertex AI backend requires langchain-google-genai installed."
        ) from exc

    return ChatGoogleGenerativeAI(
        model=model_name,
        project=project_id,
        location=region,
        vertexai=True,
        max_output_tokens=max_tokens,
    )


def _build_vertex_endpoint_model(
    *,
    endpoint_id: str,
    project_id: str,
    region: str,
    max_tokens: int,
    api_endpoint: str | None = None,
    endpoint_resource_name: str | None = None,
) -> Any:
    """Build ChatModel for a Vertex AI endpoint.

    For Model Garden models (like MedGemma), we use a custom wrapper that
    directly uses the Vertex AI SDK to avoid compatibility issues with
    the Gemini-specific ChatVertexAI class.
    """
    try:
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import BaseMessage, AIMessage
        from langchain_core.outputs import ChatResult, ChatGeneration
        from langchain_core.callbacks.manager import CallbackManagerForLLMRun
        from pydantic import Field
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Vertex AI backend requires langchain-core installed."
        ) from exc

    resolved_resource_name = endpoint_resource_name or (
        f"projects/{project_id}/locations/{region}/endpoints/{endpoint_id}"
    )

    class ModelGardenChatModel(BaseChatModel):
        """Custom ChatModel for Vertex AI Model Garden endpoints."""

        endpoint_resource_name: str
        project: str
        location: str
        max_output_tokens: int = Field(default=512)

        def _generate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: CallbackManagerForLLMRun | None = None,
            **kwargs: Any,
        ) -> ChatResult:
            from google.cloud import aiplatform

            # Initialize endpoint if not already done
            endpoint = aiplatform.Endpoint(self.endpoint_resource_name)

            # Simple prompt construction
            prompt = messages[-1].content
            if not isinstance(prompt, str):
                prompt = str(prompt)

            instances = [{"prompt": prompt}]
            parameters = {
                "max_new_tokens": self.max_output_tokens,
            }
            if stop:
                parameters["stop_sequences"] = stop

            # #region agent log
            _debug_log(
                hypothesis_id="FIX",
                location="ModelGardenChatModel._generate",
                message="Invocating Model Garden endpoint via SDK",
                data={
                    "endpoint": self.endpoint_resource_name,
                    "max_tokens": self.max_output_tokens,
                },
            )
            # #endregion

            response = endpoint.predict(instances=instances, parameters=parameters)

            # Parse response
            # MedGemma on Model Garden often returns the full prompt + completion
            text = response.predictions[0]
            if "Output:\n" in text:
                text = text.split("Output:\n")[-1].strip()
            elif prompt in text:
                text = text.replace(prompt, "", 1).strip()

            message = AIMessage(content=text)
            generation = ChatGeneration(message=message)
            return ChatResult(generations=[generation])

        @property
        def _llm_type(self) -> str:
            return "vertex_model_garden"

    return ModelGardenChatModel(
        endpoint_resource_name=resolved_resource_name,
        project=project_id,
        location=region,
        max_output_tokens=max_tokens,
    )


def _get_dedicated_endpoint_info(
    *, endpoint_id: str, project_id: str, region: str
) -> tuple[str | None, str | None]:
    """Get the dedicated endpoint URL for a Vertex AI endpoint.

    Args:
        endpoint_id: Vertex AI endpoint ID.
        project_id: GCP project ID.
        region: GCP region.

    Returns:
        Tuple of (dedicated_dns, resolved_resource_name). Each entry may be None
        if unavailable.
    """
    try:
        from google.cloud import aiplatform
    except ImportError:
        return None

    try:
        endpoint_resource_name = (
            f"projects/{project_id}/locations/{region}/endpoints/{endpoint_id}"
        )
        endpoint = aiplatform.Endpoint(endpoint_resource_name)
        # #region agent log
        _debug_log(
            hypothesis_id="D",
            location="model_factory.py:_get_dedicated_endpoint_url",
            message="Loaded endpoint resource",
            data={
                "requested_resource": endpoint_resource_name,
                "endpoint_resource_name": getattr(endpoint, "resource_name", None),
                "gca_name": getattr(getattr(endpoint, "_gca_resource", None), "name", None),
            },
        )
        # #endregion
        # #region agent log
        _debug_log(
            hypothesis_id="E",
            location="model_factory.py:_get_dedicated_endpoint_url",
            message="Deployed model details",
            data={
                "deployed_model_id": (
                    getattr(getattr(endpoint, "_gca_resource", None), "deployed_models", [None])[0]
                    and getattr(
                        getattr(endpoint, "_gca_resource", None).deployed_models[0],
                        "id",
                        None,
                    )
                ),
                "deployed_model_resource": (
                    getattr(getattr(endpoint, "_gca_resource", None), "deployed_models", [None])[0]
                    and getattr(
                        getattr(endpoint, "_gca_resource", None).deployed_models[0],
                        "model",
                        None,
                    )
                ),
            },
        )
        # #endregion
        resolved_resource_name = getattr(endpoint, "resource_name", None) or getattr(
            getattr(endpoint, "_gca_resource", None), "name", None
        )
        # Check if endpoint has dedicated DNS enabled
        if (
            hasattr(endpoint, "dedicated_endpoint_enabled")
            and endpoint.dedicated_endpoint_enabled
            and hasattr(endpoint, "dedicated_endpoint_dns")
            and endpoint.dedicated_endpoint_dns
        ):
            # dedicated_endpoint_dns is already a DNS name
            # (e.g., "endpoint-id.region-uid.prediction.vertexai.goog")
            # Return as-is (ChatVertexAI will handle the protocol)
            # #region agent log
            _debug_log(
                hypothesis_id="B",
                location="model_factory.py:_get_dedicated_endpoint_url",
                message="Dedicated endpoint DNS detected",
                data={"dedicated_dns": endpoint.dedicated_endpoint_dns},
            )
            # #endregion
            return endpoint.dedicated_endpoint_dns, resolved_resource_name
    except Exception:
        # If we can't fetch the endpoint, return None and let ChatVertexAI
        # handle it (it will use the default domain or error with a helpful message)
        # #region agent log
        _debug_log(
            hypothesis_id="B",
            location="model_factory.py:_get_dedicated_endpoint_url",
            message="Failed to fetch dedicated endpoint DNS",
            data={"endpoint_id": endpoint_id, "region": region},
        )
        # #endregion
        return None, None
    return None, resolved_resource_name


def _create_vertex_model_loader(cfg: AgentConfig) -> Callable[[], Any]:
    """Create a lazy Vertex AI model loader.

    This loader expects Application Default Credentials (ADC) to be available
    (e.g., via `gcloud auth application-default login`).

    Raises:
        ValueError: If required Vertex configuration is missing.
        ImportError: If Vertex dependencies are not installed.
    """
    project_id, region, endpoint_id, vertex_model_name = _validate_vertex_config(cfg)

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

        vertexai.init(project=project_id, location=region)
        # #region agent log
        _debug_log(
            hypothesis_id="C",
            location="model_factory.py:load_model",
            message="Vertex init complete",
            data={"project_id": project_id, "region": region},
        )
        # #endregion
        if vertex_model_name:
            model = _build_vertex_genai_model(
                model_name=vertex_model_name,
                project_id=project_id,
                region=region,
                max_tokens=cfg.max_new_tokens,
            )
        else:
            # Check for dedicated endpoint URL (from env or auto-detect)
            api_endpoint: str | None = None
            resolved_resource_name: str | None = None
            if cfg.vertex_endpoint_url:
                api_endpoint = cfg.vertex_endpoint_url
                # #region agent log
                _debug_log(
                    hypothesis_id="C",
                    location="model_factory.py:load_model",
                    message="Using api_endpoint from env",
                    data={"api_endpoint": api_endpoint},
                )
                # #endregion
            else:
                # Try to auto-detect dedicated endpoint URL and resource name
                api_endpoint, resolved_resource_name = _get_dedicated_endpoint_info(
                    endpoint_id=endpoint_id,
                    project_id=project_id,
                    region=region,
                )
                # #region agent log
                _debug_log(
                    hypothesis_id="C",
                    location="model_factory.py:load_model",
                    message="Auto-detected api_endpoint",
                    data={"api_endpoint": api_endpoint},
                )
                # #endregion
                if resolved_resource_name:
                    # #region agent log
                    _debug_log(
                        hypothesis_id="D",
                        location="model_factory.py:load_model",
                        message="Resolved endpoint resource name",
                        data={"endpoint_resource_name": resolved_resource_name},
                    )
                    # #endregion

            model = _build_vertex_endpoint_model(
                endpoint_id=endpoint_id,
                project_id=project_id,
                region=region,
                max_tokens=cfg.max_new_tokens,
                api_endpoint=api_endpoint,
                endpoint_resource_name=resolved_resource_name,
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

