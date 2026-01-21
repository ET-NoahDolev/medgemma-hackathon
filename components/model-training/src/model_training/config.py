# components/model-training/src/model_training/config.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Tuple

try:
    from peft import LoraConfig as _PeftLoraConfig, get_peft_model, TaskType as _PeftTaskType  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    _PeftLoraConfig = None  # type: ignore[assignment]
    get_peft_model = None  # type: ignore[assignment]
    _PeftTaskType = None  # type: ignore[assignment]

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    AutoModelForCausalLM = None  # type: ignore[assignment]
    AutoTokenizer = None  # type: ignore[assignment]


class TaskType(str, Enum):
    """Fallback TaskType enum used when peft isn't installed."""

    CAUSAL_LM = "CAUSAL_LM"


@dataclass
class LoraConfig:
    """Fallback LoraConfig for tests when peft isn't installed."""

    r: int
    lora_alpha: int
    target_modules: list[str]
    lora_dropout: float
    bias: str
    task_type: Any

def get_lora_config(r: int = 16, alpha: int = 32, dropout: float = 0.05) -> Any:
    """Get LoRA configuration.

    Args:
        r: LoRA attention dimension.
        alpha: LoRA alpha parameter.
        dropout: LoRA dropout probability.

    Returns:
        A LoraConfig object.
    """
    if _PeftLoraConfig is not None and _PeftTaskType is not None:
        return _PeftLoraConfig(
            r=r,
            lora_alpha=alpha,
            target_modules=["q_proj", "v_proj", "o_proj"],
            lora_dropout=dropout,
            bias="none",
            task_type=_PeftTaskType.CAUSAL_LM,
        )

    return LoraConfig(
        r=r,
        lora_alpha=alpha,
        target_modules=["q_proj", "v_proj", "o_proj"],
        lora_dropout=dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )

def load_model_and_tokenizer(
    model_name: str,
    lora_config: Any,
    load_in_8bit: bool = True
) -> Tuple[Any, Any]:
    """Load model and tokenizer, then apply LoRA.

    Args:
        model_name: Name or path of the base model.
        lora_config: LoRA configuration.
        load_in_8bit: Whether to load model in 8-bit precision.

    Returns:
        A tuple containing the model (with LoRA applied) and the tokenizer.
    """
    if AutoTokenizer is None or AutoModelForCausalLM is None or get_peft_model is None:
        raise ImportError(
            "model-training requires `transformers` and `peft` installed to load "
            "models. Install these extras to run training."
        )

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        load_in_8bit=load_in_8bit,
        device_map="auto",
    )

    model = get_peft_model(model, lora_config)

    return model, tokenizer
