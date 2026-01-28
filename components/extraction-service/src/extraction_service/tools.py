"""LangChain tools for hierarchical criteria extraction."""

from __future__ import annotations

import contextvars
import json
import logging
import threading
from pathlib import Path
from typing import Any

from inference.tools import _coerce_model_output
from jinja2 import Environment, FileSystemLoader

from extraction_service.schemas import ExtractionResult

try:
    from langchain_core.tools import tool
except ImportError:  # pragma: no cover
    from typing import Callable, ParamSpec, TypeVar

    _P = ParamSpec("_P")
    _R = TypeVar("_R")

    def tool(  # type: ignore[no-redef]  # noqa: D417
        func: Callable[_P, _R] | None = None, **_kwargs: Any
    ) -> Callable[_P, _R] | Callable[[Callable[_P, _R]], Callable[_P, _R]]:
        """Minimal fallback so this module can be imported without LangChain."""
        if func is None:

            def decorator(f: Callable[_P, _R]) -> Callable[_P, _R]:
                return f

            return decorator
        return func

logger = logging.getLogger(__name__)

# Initialize Jinja2 environment for prompt templates
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_JINJA_ENV = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)))

_clarify_cache_ctx: contextvars.ContextVar["ClarifyAmbiguityCache | None"] = (
    contextvars.ContextVar("clarify_ambiguity_cache", default=None)
)


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


def paragraph_contains_criteria(paragraph_text: str) -> bool:
    """Return True if a paragraph contains eligibility criteria.

    Args:
        paragraph_text: Paragraph text from a protocol document.

    Returns:
        True when MedGemma indicates the paragraph contains eligibility criteria.
    """
    if not paragraph_text.strip():
        return False
    prompt = (
        "Analyze this clinical trial protocol paragraph.\n"
        "Does it contain patient eligibility criteria (inclusion or exclusion)?\n"
        "Answer only YES or NO.\n\n"
        f"Paragraph: {paragraph_text}"
    )
    result = _invoke_medgemma(prompt)
    return result.strip().upper().startswith("YES")


def extract_criteria_medgemma(paragraph_text: str) -> ExtractionResult:
    """Extract criteria in a single MedGemma pass.

    Args:
        paragraph_text: Paragraph text from a protocol document.

    Returns:
        ExtractionResult with criteria and optional triplet fields.
    """
    if not paragraph_text.strip():
        return ExtractionResult(criteria=[])
    prompt = (
        "Extract all eligibility criteria from this clinical trial paragraph.\n\n"
        "For each criterion:\n"
        "1. Extract the exact text snippet\n"
        "2. Classify as \"inclusion\" or \"exclusion\"\n"
        "3. Provide a confidence score between 0.0 and 1.0\n"
        "4. If possible, extract entity, relation, value, and unit\n\n"
        "Return ONLY a JSON object matching this shape:\n"
        "{\"criteria\":[{\"text\":\"...\",\"criterion_type\":\"inclusion\","
        "\"confidence\":0.85,\"entity\":\"age\",\"relation\":\">=\","
        "\"value\":\"18\",\"unit\":\"years\"}]}\n\n"
        f"Paragraph: {paragraph_text}"
    )
    result = _invoke_medgemma(prompt)
    try:
        payload = json.loads(result)
    except json.JSONDecodeError as exc:
        raise ValueError("MedGemma returned invalid JSON for extraction.") from exc
    if not isinstance(payload, dict):
        raise ValueError("MedGemma extraction payload is not an object.")
    return ExtractionResult(**payload)


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


def extract_triplets_batch(criteria_texts: list[str]) -> list[dict[str, Any]]:
    """Extract entity/relation/value triplets for multiple criteria in one call.

    Args:
        criteria_texts: Criterion text strings.

    Returns:
        List of triplet dictionaries in the same order as inputs.
    """
    if not criteria_texts:
        return []
    prompt = (
        "Extract entity/relation/value triplets for each criterion below.\n\n"
        "Return ONLY a JSON array matching input order. Each item should be an "
        "object with keys: entity, relation, value, unit.\n\n"
        "Criteria:\n"
        + "\n".join(
            f"{index + 1}. {text}" for index, text in enumerate(criteria_texts)
        )
    )
    result = _invoke_medgemma(prompt)
    try:
        payload = json.loads(result)
    except json.JSONDecodeError as exc:
        raise ValueError("MedGemma returned invalid JSON for batch triplets.") from exc
    if not isinstance(payload, list):
        raise ValueError("MedGemma batch triplet payload is not a list.")
    normalized: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            normalized.append(_normalize_triplet_payload(item))
        else:
            normalized.append({})
    return normalized


def _clarify_ambiguity_impl(question: str, text: str) -> str:
    """Invoke MedGemma to clarify an ambiguous criterion.

    Used by clarify_ambiguity and by ClarifyAmbiguityCache.
    """
    template = _JINJA_ENV.get_template("clarify_ambiguity.j2")
    prompt = template.render(question=question, text=text)
    return _invoke_medgemma(prompt)


@tool
def clarify_ambiguity(question: str, text: str) -> str:
    """Clarify an ambiguous criterion with a targeted question.

    Args:
        question: Clarification question to answer.
        text: The ambiguous text segment.

    Returns:
        Clarification response text.
    """
    return _clarify_ambiguity_impl(question, text)


class ClarifyAmbiguityCache:
    """Cache clarify_ambiguity by (question, text) to avoid repeated calls."""

    def __init__(self) -> None:
        """Initialize an empty cache."""
        self._cache: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()

    def clarify(self, question: str, text: str) -> str:
        """Return clarification for (question, text), using cache on repeated calls."""
        key = (question.strip().lower(), text.strip().lower())
        with self._lock:
            cached = self._cache.get(key)
        if cached is not None:
            logger.debug("Returning cached clarification for: %s", question[:50])
            return f"[Already answered] {cached}"
        result = _clarify_ambiguity_impl(question, text)
        with self._lock:
            self._cache[key] = result
        return result

    def reset(self) -> None:
        """Clear the cache (e.g. between paragraphs)."""
        with self._lock:
            self._cache.clear()


def set_clarify_cache(cache: ClarifyAmbiguityCache | None) -> None:
    """Set the current clarify cache for this async context."""
    _clarify_cache_ctx.set(cache)


def make_clarify_ambiguity_tool() -> Any:
    """Return a LangChain tool that delegates to the active cache."""

    @tool
    def clarify_ambiguity_cached(question: str, text: str) -> str:
        """Clarify an ambiguous criterion (cached per paragraph)."""
        cache = _clarify_cache_ctx.get()
        if cache is None:
            return _clarify_ambiguity_impl(question, text)
        return cache.clarify(question, text)

    return clarify_ambiguity_cached
