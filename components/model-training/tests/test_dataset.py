# components/model-training/tests/test_dataset.py
import pytest
import json
from pathlib import Path
from model_training.dataset import load_training_data, format_extraction_prompt, format_grounding_prompt

@pytest.fixture
def sample_data(tmp_path):
    data = [
        {
            "criterion_text": "Age >= 18",
            "criterion_type": "inclusion",
            "snomed_codes": ["12345"],
            "field_mapping": "demographics.age|>=|18"
        },
        {
            "criterion_text": "Pregnant",
            "criterion_type": "exclusion",
            "snomed_codes": [],
            "field_mapping": None
        }
    ]
    file_path = tmp_path / "train.jsonl"
    with open(file_path, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")
    return file_path

def test_load_training_data(sample_data):
    dataset = load_training_data(str(sample_data))
    assert len(dataset) == 2
    assert dataset[0]["criterion_text"] == "Age >= 18"
    assert dataset[1]["criterion_type"] == "exclusion"

def test_format_extraction_prompt():
    example = {
        "criterion_text": "Age >= 18",
        "criterion_type": "inclusion"
    }
    formatted = format_extraction_prompt(example)
    prompt = formatted["text"]
    
    assert "<|im_start|>system" in prompt
    assert "clinical trial criteria extraction assistant" in prompt
    assert "Criterion text: Age >= 18" in prompt
    assert "Type: inclusion" in prompt

def test_format_grounding_prompt_with_codes():
    example = {
        "criterion_text": "Age >= 18",
        "criterion_type": "inclusion",
        "snomed_codes": ["12345", "67890"],
        "field_mapping": "demographics.age|>=|18"
    }
    formatted = format_grounding_prompt(example)
    prompt = formatted["text"]
    
    assert "<|im_start|>system" in prompt
    assert "clinical terminology mapping assistant" in prompt
    assert "Criterion: Age >= 18" in prompt
    assert "Type: inclusion" in prompt
    assert "SNOMED codes: 12345, 67890" in prompt
    assert "Field mapping: demographics.age|>=|18" in prompt

def test_format_grounding_prompt_no_codes():
    example = {
        "criterion_text": "Unknown condition",
        "criterion_type": "inclusion",
        "snomed_codes": [],
        "field_mapping": None
    }
    formatted = format_grounding_prompt(example)
    prompt = formatted["text"]
    
    assert "SNOMED codes: None" in prompt
    assert "Field mapping: None" in prompt
