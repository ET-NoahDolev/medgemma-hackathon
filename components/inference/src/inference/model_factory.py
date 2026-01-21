"""Factory for creating MedGemma model loaders.

The factory returns a lazy loader (callable). Importing this module should remain
lightweight; heavyweight ML dependencies are imported only when the loader runs.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from inference.config import AgentConfig


def create_model_loader(config: AgentConfig | None = None) -> Callable[[], Any]:
    """Create a lazy MedGemma model loader.

    Args:
        config: Agent configuration. Defaults to `AgentConfig.from_env()`.

    Returns:
        Callable that loads and returns a LangChain chat model when invoked.
    """
    cfg = config or AgentConfig.from_env()
    cache: list[Any] = []

    def load_model() -> Any:
        if cache:
            return cache[0]

        # Ensure Hugging Face token is available for authentication
        # transformers/huggingface_hub looks for HF_TOKEN or HUGGINGFACEHUB_API_TOKEN
        hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
        if hf_token:
            # Set both environment variable names to ensure compatibility
            os.environ["HF_TOKEN"] = hf_token
            os.environ["HUGGINGFACEHUB_API_TOKEN"] = hf_token
            # Also ensure huggingface_hub uses the token
            try:
                from huggingface_hub import login  # type: ignore[import-not-found]

                login(token=hf_token, add_to_git_credential=False)
            except Exception:
                # If login fails, continue anyway - token is in env vars
                pass

        try:
            import torch  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "Torch is required to load MedGemma. Install inference ML dependencies."
            ) from exc

        try:
            from langchain_huggingface import (  # type: ignore[import-not-found]
                ChatHuggingFace,
                HuggingFacePipeline,
            )
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "langchain-huggingface is required to load MedGemma. "
                "Install inference ML dependencies."
            ) from exc

        from transformers import BitsAndBytesConfig  # type: ignore[import-not-found]

        # Check if model is already cached to avoid re-downloading
        model_cached = False
        try:
            from huggingface_hub import try_to_load_from_cache  # type: ignore[import-not-found]

            # Check for key files that indicate model is cached
            config_path = try_to_load_from_cache(
                repo_id=cfg.model_path, filename="config.json", revision="main"
            )
            # If config exists, assume model files are cached (transformers handles this)
            model_cached = config_path is not None
        except Exception:
            # If cache check fails, proceed with normal download
            model_cached = False

        model_kwargs: dict[str, Any] = {
            "device_map": "auto",
            "dtype": torch.bfloat16,
        }

        quant = (cfg.quantization or "none").lower()
        if quant == "4bit":
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
            )
        elif quant == "8bit":
            model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        elif quant == "none":
            pass
        else:
            raise ValueError(f"Unsupported quantization: {cfg.quantization}")

        # Prepare kwargs for HuggingFacePipeline.from_model_id
        # If model is cached, use local_files_only to avoid network calls
        pipeline_kwargs_base: dict[str, Any] = {"max_new_tokens": cfg.max_new_tokens}
        extra_kwargs: dict[str, Any] = {}
        if model_cached:
            # Pass local_files_only via **kwargs to avoid re-downloading
            extra_kwargs["local_files_only"] = True

        # Try loading with local_files_only first if cached, fall back to normal if it fails
        try:
            llm = HuggingFacePipeline.from_model_id(
                model_id=cfg.model_path,
                task="text-generation",
                model_kwargs=model_kwargs,
                pipeline_kwargs=pipeline_kwargs_base,
                **extra_kwargs,
            )
        except Exception as e:
            # If local_files_only=True failed (e.g., missing files), retry without it
            if model_cached and ("local_files_only" in str(e).lower() or "not found" in str(e).lower()):
                # Remove local_files_only and retry (will download missing files)
                extra_kwargs.pop("local_files_only", None)
                llm = HuggingFacePipeline.from_model_id(
                    model_id=cfg.model_path,
                    task="text-generation",
                    model_kwargs=model_kwargs,
                    pipeline_kwargs=pipeline_kwargs_base,
                    **extra_kwargs,
                )
            else:
                raise

        model = ChatHuggingFace(llm=llm)
        cache.append(model)
        return model

    return load_model

