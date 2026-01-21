"""Factory for creating MedGemma model loaders.

The factory returns a lazy loader (callable). Importing this module should remain
lightweight; heavyweight ML dependencies are imported only when the loader runs.
"""

from __future__ import annotations

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

        model_kwargs: dict[str, Any] = {
            "device_map": "auto",
            "torch_dtype": torch.bfloat16,
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

        llm = HuggingFacePipeline.from_model_id(
            model_id=cfg.model_path,
            task="text-generation",
            model_kwargs=model_kwargs,
            pipeline_kwargs={"max_new_tokens": cfg.max_new_tokens},
        )
        model = ChatHuggingFace(llm=llm)
        cache.append(model)
        return model

    return load_model

