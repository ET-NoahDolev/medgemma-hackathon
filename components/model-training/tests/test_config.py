# components/model-training/tests/test_config.py
import pytest
from unittest.mock import patch, MagicMock
from model_training.config import get_lora_config, load_model_and_tokenizer
from peft import TaskType

def test_get_lora_config():
    config = get_lora_config(r=16, alpha=32, dropout=0.05)
    
    assert config.r == 16
    assert config.lora_alpha == 32
    assert config.lora_dropout == 0.05
    assert config.task_type == TaskType.CAUSAL_LM
    assert "q_proj" in config.target_modules

@patch("model_training.config.AutoTokenizer")
@patch("model_training.config.AutoModelForCausalLM")
@patch("model_training.config.get_peft_model")
def test_load_model_and_tokenizer(mock_get_peft, mock_automodel, mock_tokenizer):
    mock_model = MagicMock()
    mock_automodel.from_pretrained.return_value = mock_model
    
    mock_tok = MagicMock()
    mock_tokenizer.from_pretrained.return_value = mock_tok
    
    lora_config = MagicMock()
    
    model, tokenizer = load_model_and_tokenizer("google/medgemma-4b", lora_config)
    
    mock_tokenizer.from_pretrained.assert_called_once_with("google/medgemma-4b")
    mock_automodel.from_pretrained.assert_called_once()
    mock_get_peft.assert_called_once_with(mock_model, lora_config)
    assert model == mock_get_peft.return_value
    assert tokenizer == mock_tok
