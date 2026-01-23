# components/model-training/src/model_training/dataset.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from jinja2 import Environment, FileSystemLoader

try:
    # Optional dependency (used in real training runs)
    from datasets import Dataset as _HfDataset  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    _HfDataset = None  # type: ignore[assignment]


@dataclass
class Dataset:
    """Lightweight Dataset fallback compatible with our tests/notebooks.

    This mirrors the small subset of the HuggingFace `datasets.Dataset` API we use:
    - `from_list`
    - `__len__`, `__getitem__`
    - `map` (merges returned dict into each example)
    """

    _items: list[dict[str, Any]]

    @classmethod
    def from_list(cls, items: list[dict[str, Any]]) -> "Dataset":
        if _HfDataset is not None:
            return _HfDataset.from_list(items)  # type: ignore[return-value]
        return cls(items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        return self._items[idx]

    def map(self, fn: Callable[[dict[str, Any]], dict[str, Any]]) -> "Dataset":
        mapped: list[dict[str, Any]] = []
        for item in self._items:
            mapped.append({**item, **fn(item)})
        return Dataset.from_list(mapped)

def load_training_data(path: str) -> Dataset:
    """Load training data from a JSONL file.

    Args:
        path: Path to the JSONL file.

    Returns:
        A generic HuggingFace Dataset containing the loaded examples.
    """
    examples: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                examples.append(json.loads(line))
    return Dataset.from_list(examples)


# Initialize Jinja2 environment for prompt templates
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_JINJA_ENV = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)))


def format_extraction_prompt(example: dict[str, Any]) -> dict[str, str]:
    """Format prompt for the extraction task (Task A).

    Args:
        example: A dictionary containing 'criterion_text' and 'criterion_type'.

    Returns:
        A dictionary with a single key 'text' containing the formatted prompt.
    """
    system_tpl = _JINJA_ENV.get_template("extraction_system.j2")
    user_tpl = _JINJA_ENV.get_template("extraction_user.j2")
    assistant_tpl = _JINJA_ENV.get_template("extraction_assistant.j2")

    system_content = system_tpl.render()
    user_content = user_tpl.render(criterion_text=example["criterion_text"])
    assistant_content = assistant_tpl.render(criterion_type=example["criterion_type"])

    prompt = f"""<|im_start|>system
{system_content}
<|im_end|>
<|im_start|>user
{user_content}
<|im_end|>
<|im_start|>assistant
{assistant_content}
<|im_end|>"""
    return {"text": prompt}

def format_grounding_prompt(example: dict[str, Any]) -> dict[str, str]:
    """Format prompt for the grounding task (Task B).

    Args:
        example: A dictionary containing 'criterion_text', 'criterion_type',
                 'snomed_codes', and 'field_mapping'.

    Returns:
        A dictionary with a single key 'text' containing the formatted prompt.
    """
    snomed_codes = example.get("snomed_codes")
    if snomed_codes:
        snomed_str = ", ".join(snomed_codes)
    else:
        snomed_str = "None"

    mapping_str = example.get("field_mapping") or "None"

    system_tpl = _JINJA_ENV.get_template("grounding_system.j2")
    user_tpl = _JINJA_ENV.get_template("grounding_user.j2")
    assistant_tpl = _JINJA_ENV.get_template("grounding_assistant.j2")

    system_content = system_tpl.render()
    user_content = user_tpl.render(
        criterion_text=example["criterion_text"], criterion_type=example["criterion_type"]
    )
    assistant_content = assistant_tpl.render(
        snomed_codes=snomed_str, field_mapping=mapping_str
    )

    prompt = f"""<|im_start|>system
{system_content}
<|im_end|>
<|im_start|>user
{user_content}
<|im_end|>
<|im_start|>assistant
{assistant_content}
<|im_end|>"""
    return {"text": prompt}


def format_for_vertex(example: dict[str, Any]) -> dict[str, Any]:
    """Format an example into Vertex AI SFT JSONL format.

    Vertex managed tuning expects each JSONL line to include a `messages` array
    with role/content objects. This helper supports our two main tasks:
    - extraction (Task A)
    - grounding (Task B)

    The output is suitable for writing to JSONL and uploading to GCS.

    Args:
        example: An example dictionary. For extraction, must include
            `criterion_text` and `criterion_type`. For grounding, it should also
            include `snomed_codes` and `field_mapping`.

    Returns:
        Dict with a single key `messages` containing the conversation.
    """
    if "snomed_codes" in example or "field_mapping" in example:
        return _format_grounding_for_vertex(example)
    return _format_extraction_for_vertex(example)


def _format_extraction_for_vertex(example: dict[str, Any]) -> dict[str, Any]:
    if not str(example.get("criterion_text", "")).strip():
        raise ValueError("criterion_text is required for extraction examples")
    if not str(example.get("criterion_type", "")).strip():
        raise ValueError("criterion_type is required for extraction examples")

    system_tpl = _JINJA_ENV.get_template("extraction_system.j2")
    user_tpl = _JINJA_ENV.get_template("extraction_user.j2")
    assistant_tpl = _JINJA_ENV.get_template("extraction_assistant.j2")

    return {
        "messages": [
            {
                "role": "system",
                "content": system_tpl.render(),
            },
            {
                "role": "user",
                "content": user_tpl.render(criterion_text=example["criterion_text"]),
            },
            {
                "role": "assistant",
                "content": assistant_tpl.render(criterion_type=example["criterion_type"]),
            },
        ]
    }


def _format_grounding_for_vertex(example: dict[str, Any]) -> dict[str, Any]:
    if not str(example.get("criterion_text", "")).strip():
        raise ValueError("criterion_text is required for grounding examples")
    if not str(example.get("criterion_type", "")).strip():
        raise ValueError("criterion_type is required for grounding examples")

    snomed_codes = example.get("snomed_codes") or []
    snomed_str = ", ".join(snomed_codes) if isinstance(snomed_codes, list) else str(snomed_codes)
    if not snomed_str.strip():
        snomed_str = "None"
    mapping_str = str(example.get("field_mapping") or "None")

    system_tpl = _JINJA_ENV.get_template("grounding_system.j2")
    user_tpl = _JINJA_ENV.get_template("grounding_user.j2")
    assistant_tpl = _JINJA_ENV.get_template("grounding_assistant.j2")

    return {
        "messages": [
            {
                "role": "system",
                "content": system_tpl.render(),
            },
            {
                "role": "user",
                "content": user_tpl.render(
                    criterion_text=example["criterion_text"],
                    criterion_type=example["criterion_type"],
                ),
            },
            {
                "role": "assistant",
                "content": assistant_tpl.render(
                    snomed_codes=snomed_str, field_mapping=mapping_str
                ),
            },
        ]
    }
