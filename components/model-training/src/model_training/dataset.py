# components/model-training/src/model_training/dataset.py
import json
from datasets import Dataset

def load_training_data(path: str) -> Dataset:
    """Load training data from a JSONL file.

    Args:
        path: Path to the JSONL file.

    Returns:
        A generic HuggingFace Dataset containing the loaded examples.
    """
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                examples.append(json.loads(line))
    return Dataset.from_list(examples)

def format_extraction_prompt(example: dict) -> dict:
    """Format prompt for the extraction task (Task A).

    Args:
        example: A dictionary containing 'criterion_text' and 'criterion_type'.

    Returns:
        A dictionary with a single key 'text' containing the formatted prompt.
    """
    prompt = f"""<|im_start|>system
You are a clinical trial criteria extraction assistant. Extract and classify the criterion.
<|im_end|>
<|im_start|>user
Criterion text: {example['criterion_text']}
<|im_end|>
<|im_start|>assistant
Type: {example['criterion_type']}
<|im_end|>"""
    return {"text": prompt}

def format_grounding_prompt(example: dict) -> dict:
    """Format prompt for the grounding task (Task B).

    Args:
        example: A dictionary containing 'criterion_text', 'criterion_type',
                 'snomed_codes', and 'field_mapping'.

    Returns:
        A dictionary with a single key 'text' containing the formatted prompt.
    """
    snomed_codes = example.get('snomed_codes')
    if snomed_codes:
        snomed_str = ", ".join(snomed_codes)
    else:
        snomed_str = "None"
        
    mapping_str = example.get('field_mapping') or "None"
    
    prompt = f"""<|im_start|>system
You are a clinical terminology mapping assistant. Map the criterion to SNOMED codes and field mappings.
<|im_end|>
<|im_start|>user
Criterion: {example['criterion_text']}
Type: {example['criterion_type']}
<|im_end|>
<|im_start|>assistant
SNOMED codes: {snomed_str}
Field mapping: {mapping_str}
<|im_end|>"""
    return {"text": prompt}
