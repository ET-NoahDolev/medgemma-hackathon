"""LangChain tools for hierarchical criteria extraction."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from inference.tools import _coerce_model_output
from jinja2 import Environment, FileSystemLoader

try:
    from langchain_core.tools import tool
except ImportError:  # pragma: no cover
    # Minimal fallback so this module can be imported without LangChain installed.
    def _tool(func=None, **_kwargs):  # type: ignore[no-redef]
        if func is None:
            return lambda f: f
        return func

    tool = _tool  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Initialize Jinja2 environment for prompt templates
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_JINJA_ENV = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)))


RELATION_NORMALIZATION = {
    "older than": ">",
    "younger than": "<",
    "at least": ">=",
    "no more than": "<=",
    "less than": "<",
    "greater than": ">",
    "diagnosed with": "present",
    "without history of": "absent",
    "between": "between",
    "within range": "between",
    "is not": "!=",
    "is": "=",
}
def _invoke_medgemma(prompt: str) -> str:
    from inference import AgentConfig, create_model_loader

    cfg = AgentConfig.from_env()
    model = create_model_loader(cfg)()
    try:
        result = model.invoke([("user", prompt)])
        return _coerce_model_output(result)
    except Exception as exc:
        logger.error("MedGemma tool invocation failed: %s", exc, exc_info=True)
        raise


def _normalize_relation(relation: str | None) -> str | None:
    if relation is None:
        return None
    cleaned = relation.strip().lower()
    if not cleaned:
        return None
    if cleaned in RELATION_NORMALIZATION:
        return RELATION_NORMALIZATION[cleaned]
    return relation


def _normalize_triplet_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "triplets" in payload and isinstance(payload["triplets"], list):
        normalized_triplets = []
        for item in payload["triplets"]:
            if not isinstance(item, dict):
                continue
            normalized_triplets.append(
                {
                    "entity": item.get("entity"),
                    "relation": _normalize_relation(item.get("relation")),
                    "value": item.get("value"),
                    "unit": item.get("unit"),
                    "modifiers": item.get("modifiers", []),
                }
            )
        return {
            "triplets": normalized_triplets,
            "logical_operator": payload.get("logical_operator"),
        }

    return {
        "entity": payload.get("entity"),
        "relation": _normalize_relation(payload.get("relation")),
        "value": payload.get("value"),
        "unit": payload.get("unit"),
        "modifiers": payload.get("modifiers", []),
    }


@tool
def extract_triplet(text: str) -> str:
    """Extract entity/relation/value triplets from criterion text.

    Args:
        text: Criterion text, e.g., "Age 18 years or older".

    Returns:
        JSON string with entity/relation/value/unit or list of triplets.
    """
    template = _JINJA_ENV.get_template("extract_triplet.j2")
    prompt = template.render(text=text)
    result = _invoke_medgemma(prompt)
    try:
        payload = json.loads(result)
    except json.JSONDecodeError:
        logger.debug("Triplet extraction returned non-JSON output.")
        return result

    if not isinstance(payload, dict):
        return result

    normalized = _normalize_triplet_payload(payload)
    return json.dumps(normalized, separators=(",", ":"))


@tool
def clarify_ambiguity(question: str, text: str) -> str:
    """Clarify an ambiguous criterion with a targeted question.

    Args:
        question: Clarification question to answer.
        text: The ambiguous text segment.

    Returns:
        Clarification response text.
    """
    template = _JINJA_ENV.get_template("clarify_ambiguity.j2")
    prompt = template.render(question=question, text=text)
    return _invoke_medgemma(prompt)
