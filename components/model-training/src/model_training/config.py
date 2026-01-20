# components/model-training/src/model_training/config.py
from typing import Tuple
from peft import LoraConfig, get_peft_model, TaskType, PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer

def get_lora_config(r: int = 16, alpha: int = 32, dropout: float = 0.05) -> LoraConfig:
    """Get LoRA configuration.

    Args:
        r: LoRA attention dimension.
        alpha: LoRA alpha parameter.
        dropout: LoRA dropout probability.

    Returns:
        A LoraConfig object.
    """
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
    lora_config: LoraConfig,
    load_in_8bit: bool = True
) -> Tuple[PreTrainedModel, PreTrainedTokenizer]:
    """Load model and tokenizer, then apply LoRA.

    Args:
        model_name: Name or path of the base model.
        lora_config: LoRA configuration.
        load_in_8bit: Whether to load model in 8-bit precision.

    Returns:
        A tuple containing the model (with LoRA applied) and the tokenizer.
    """
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        load_in_8bit=load_in_8bit,
        device_map="auto",
    )
    
    model = get_peft_model(model, lora_config)
    
    return model, tokenizer
