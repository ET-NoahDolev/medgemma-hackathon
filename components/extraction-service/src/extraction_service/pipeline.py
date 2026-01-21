"""Extraction pipeline for MedGemma Task A.

This module provides:
- A baseline regex-based extractor (fast, deterministic).
- An optional MedGemma-based extractor (via the shared `inference` component).

The public API remains:
- `extract_criteria(document_text)`
- `extract_criteria_stream(document_text)`
"""

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator

from shared.models import Criterion

logger = logging.getLogger(__name__)


def _criteria_from_extraction_result(result: Any) -> list[Criterion]:
    """Convert an ExtractionResult-like object into Criterion list."""
    extracted: list[Criterion] = []
    for item in getattr(result, "criteria", []) or []:
        text = _normalize_candidate(getattr(item, "text", ""))
        if not is_valid_criterion_candidate(text):
            continue
        extracted.append(
            Criterion(
                id="",
                text=text,
                criterion_type=getattr(item, "criterion_type", "inclusion"),
                confidence=float(getattr(item, "confidence", 0.75)),
                snomed_codes=[],
                evidence_spans=[],
            )
        )
    return extracted


@dataclass(frozen=True)
class ExtractionConfig:
    """Configuration for extraction.

    Attributes:
        use_model: Whether to attempt MedGemma-based extraction.
        model_path: HuggingFace model ID or local model path.
        quantization: Quantization level ("4bit", "8bit", or "none").
    """

    use_model: bool = True
    model_path: str = "google/medgemma-4b-it"
    quantization: str = "4bit"

    @classmethod
    def from_env(cls) -> "ExtractionConfig":
        """Create config from environment variables."""
        use_model = os.getenv("USE_MODEL_EXTRACTION", "true").lower() == "true"
        return cls(
            use_model=use_model,
            model_path=os.getenv("MEDGEMMA_MODEL_PATH", cls.model_path),
            quantization=os.getenv("MEDGEMMA_QUANTIZATION", cls.quantization),
        )


class ExtractionPipeline:
    """Extraction pipeline with optional MedGemma-based extraction."""

    def __init__(self, config: ExtractionConfig | None = None) -> None:
        """Initialize the extraction pipeline."""
        self.config = config or ExtractionConfig.from_env()
        self._extract_agent: Any | None = None

    def _get_extract_agent(self) -> Any:
        """Lazily create the MedGemma extraction agent."""
        if self._extract_agent is not None:
            return self._extract_agent

        from inference import AgentConfig, create_model_loader, create_react_agent

        prompts_dir = Path(__file__).parent / "prompts"
        base_cfg = AgentConfig.from_env()
        agent_cfg = AgentConfig(
            backend=base_cfg.backend,
            model_path=self.config.model_path or base_cfg.model_path,
            quantization=self.config.quantization or base_cfg.quantization,
            max_new_tokens=base_cfg.max_new_tokens,
            gcp_project_id=base_cfg.gcp_project_id,
            gcp_region=base_cfg.gcp_region,
            vertex_endpoint_id=base_cfg.vertex_endpoint_id,
        )
        model_loader = create_model_loader(agent_cfg)
        # Import locally to keep baseline users lightweight.
        from extraction_service.schemas import ExtractionResult

        self._extract_agent = create_react_agent(
            model_loader=model_loader,
            prompts_dir=prompts_dir,
            tools=[],
            response_schema=ExtractionResult,
            system_template="extraction_system.j2",
            user_template="extraction_user.j2",
        )
        return self._extract_agent

    def extract_criteria_stream(self, document_text: str) -> Iterator[Criterion]:
        """Stream atomic inclusion/exclusion criteria from protocol text."""
        if not document_text.strip():
            raise ValueError("document_text is required")

        if self.config.use_model:
            try:
                # Model extraction returns a list; stream it for API consistency.
                criteria = self.extract_criteria(document_text)
                yield from criteria
                return
            except Exception as exc:
                logger.warning("Model extraction failed; using baseline: %s", exc)

        yield from _extract_criteria_baseline_stream(document_text)

    async def extract_criteria_async(self, document_text: str) -> list[Criterion]:
        """Extract criteria using async model invocation when available.

        This is the preferred entrypoint when already running inside an asyncio loop
        (e.g., FastAPI background tasks). It avoids calling `anyio.run()`, which
        raises "Already running asyncio in this thread".
        """
        if not document_text.strip():
            raise ValueError("document_text is required")

        if not self.config.use_model:
            return _extract_criteria_baseline(document_text)

        try:
            agent = self._get_extract_agent()
            result = await agent({"document_text": document_text})
            extracted = _criteria_from_extraction_result(result)
            if extracted:
                return extracted
        except Exception as exc:
            logger.warning("Model extraction failed; using baseline: %s", exc)

        return _extract_criteria_baseline(document_text)

    def extract_criteria(self, document_text: str) -> list[Criterion]:
        """Extract atomic inclusion/exclusion criteria from protocol text."""
        if not document_text.strip():
            raise ValueError("document_text is required")

        if not self.config.use_model:
            return _extract_criteria_baseline(document_text)

        try:
            agent = self._get_extract_agent()
            # The agent is an async callable; run it via anyio from sync context.
            from anyio import run  # type: ignore[import-not-found]

            from extraction_service.schemas import ExtractionResult

            result: ExtractionResult = run(  # type: ignore[no-untyped-call]
                agent, {"document_text": document_text}
            )
            extracted = _criteria_from_extraction_result(result)
            if extracted:
                return extracted
        except Exception as exc:
            logger.warning("Model extraction failed; using baseline: %s", exc)

        return _extract_criteria_baseline(document_text)


def _extract_criteria_baseline_stream(document_text: str) -> Iterator[Criterion]:
    """Baseline extraction implementation using regex (streaming)."""
    if not document_text.strip():
        raise ValueError("document_text is required")

    sections = detect_sections(document_text)

    # Track seen text to deduplicate if needed, essentially just yielding
    for section_type, section_text in sections.items():
        sentences = split_into_candidate_sentences(section_text)
        for sentence in sentences:
            if not is_valid_criterion_candidate(sentence):
                continue
            criterion_type = classify_criterion_type(sentence, section=section_type)
            confidence = 0.9 if section_type != "unknown" else 0.7
            yield Criterion(
                id="",
                text=sentence,
                criterion_type=criterion_type,
                confidence=confidence,
                snomed_codes=[],
                evidence_spans=[],
            )


def _extract_criteria_baseline(document_text: str) -> list[Criterion]:
    """Baseline extraction implementation using regex (legacy list return)."""
    return list(_extract_criteria_baseline_stream(document_text))


def extract_criteria_stream(document_text: str) -> Iterator[Criterion]:
    """Stream atomic inclusion/exclusion criteria from protocol text.

    Uses MedGemma if enabled, else falls back to baseline.

    Args:
        document_text: Raw protocol text or extracted PDF text.

    Yields:
         Extracted criteria with type and confidence scores.
    """
    yield from get_extraction_pipeline().extract_criteria_stream(document_text)


def extract_criteria(document_text: str) -> list[Criterion]:
    r"""Extract atomic inclusion/exclusion criteria from protocol text.

    Uses MedGemma if enabled, else falls back to baseline.

    Args:
        document_text: Raw protocol text or extracted PDF text.

    Returns:
        A list of extracted criteria with type and confidence scores.

    Raises:
        ValueError: If the document text is empty or not parseable.

    Examples:
        >>> items = extract_criteria("Inclusion Criteria:\\n- Age >= 18 years.")
        >>> len(items) >= 1
        True

    Notes:
        This function uses MedGemma if USE_MODEL_EXTRACTION=true, otherwise it
        uses the baseline regex extractor.
    """
    return get_extraction_pipeline().extract_criteria(document_text)


async def extract_criteria_async(document_text: str) -> list[Criterion]:
    """Async variant of `extract_criteria` for callers already in an event loop."""
    return await get_extraction_pipeline().extract_criteria_async(document_text)


_PIPELINE: ExtractionPipeline | None = None


def get_extraction_pipeline(
    config: ExtractionConfig | None = None,
) -> ExtractionPipeline:
    """Get or create a singleton extraction pipeline.

    Args:
        config: Optional configuration override. If provided, returns a new instance.
    """
    global _PIPELINE
    if config is not None:
        return ExtractionPipeline(config=config)
    if _PIPELINE is None:
        _PIPELINE = ExtractionPipeline()
    return _PIPELINE


def split_into_candidate_sentences(text: str) -> list[str]:
    """Split text into candidate criterion sentences.

    Args:
        text: Section text to split.

    Returns:
        List of candidate sentences.
    """
    if not text.strip():
        return []

    if "\n" not in text and (
        INLINE_INCLUSION.search(text) or INLINE_EXCLUSION.search(text)
    ):
        return _split_inline_criteria(text)

    lines = text.split("\n")
    candidates: list[str] = []
    for line in lines:
        cleaned = _normalize_candidate(BULLET_PATTERN.sub("", line))
        if not cleaned:
            continue
        if INCLUSION_HEADER.match(cleaned) or EXCLUSION_HEADER.match(cleaned):
            continue
        candidates.append(cleaned)
    return candidates


def _split_inline_criteria(text: str) -> list[str]:
    """Split inline Inclusion/Exclusion sentences into criteria."""
    normalized = text.replace("\n", " ").strip()
    raw_sentences = [segment.strip() for segment in normalized.split(".")]
    candidates: list[str] = []
    for sentence in raw_sentences:
        if not sentence:
            continue
        lowered = sentence.lower()
        if lowered.startswith("inclusion:"):
            sentence = sentence[len("inclusion:") :].strip()
        elif lowered.startswith("exclusion:"):
            sentence = sentence[len("exclusion:") :].strip()
        sentence = _normalize_candidate(sentence)
        if sentence:
            candidates.append(sentence)
    return candidates


def _normalize_candidate(text: str) -> str:
    """Normalize candidate criteria text."""
    return text.strip().rstrip(".")


_PAGE_NUMBER_PATTERN = re.compile(r"^\s*\d+\s*$")
_NUMERIC_RANGE_PATTERN = re.compile(r"^\s*\d+\s*[-–]\s*\d+\s*$")
_CITATION_YEAR_VOL_PAGES_PATTERN = re.compile(
    r"\b(19|20)\d{2}\s*;\s*\d+\s*:\s*\d+(?:\s*[-–]\s*\d+)?\b", re.IGNORECASE
)
_CITATION_MARKERS_PATTERN = re.compile(
    r"\b(?:et\s+al\.?|doi:|pmid:|issn:|vol\.|no\.|pp\.|pages?)\b", re.IGNORECASE
)


def is_valid_criterion_candidate(text: str) -> bool:
    """Heuristically filter out noise that is not a criterion.

    Args:
        text: Candidate text.

    Returns:
        True if the text looks like an inclusion/exclusion criterion.
    """
    cleaned = text.strip()
    if not cleaned:
        return False
    if _PAGE_NUMBER_PATTERN.match(cleaned):
        return False
    if _NUMERIC_RANGE_PATTERN.match(cleaned):
        return False
    if not re.search(r"[A-Za-z]", cleaned):
        return False
    if _CITATION_YEAR_VOL_PAGES_PATTERN.search(cleaned):
        return False
    if _CITATION_MARKERS_PATTERN.search(cleaned):
        return False
    return True


def classify_criterion_type(candidate_text: str, section: str = "unknown") -> str:
    """Classify criterion as inclusion or exclusion.

    Args:
        candidate_text: Criterion text.
        section: Section context ("inclusion", "exclusion", or "unknown").

    Returns:
        Either "inclusion" or "exclusion".
    """
    if not candidate_text.strip():
        raise ValueError("candidate_text is required")

    lowered = candidate_text.lower()
    for keyword in EXCLUSION_KEYWORDS:
        if keyword in lowered:
            return "exclusion"

    if section == "exclusion":
        return "exclusion"

    return "inclusion"


INCLUSION_HEADER = re.compile(
    r"(?:^|\n)\s*(?:inclusion\s*criteria|eligibility\s*criteria|include)\s*:?\s*(?:\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
EXCLUSION_HEADER = re.compile(
    r"(?:^|\n)\s*(?:exclusion\s*criteria|ineligibility\s*criteria|exclude)\s*:?\s*(?:\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
BULLET_PATTERN = re.compile(r"^\s*(?:[-•*]|\d+[.)\]]|\([a-z]\))\s*", re.MULTILINE)
INLINE_INCLUSION = re.compile(r"\binclusion\b\s*:", re.IGNORECASE)
INLINE_EXCLUSION = re.compile(r"\bexclusion\b\s*:", re.IGNORECASE)

EXCLUSION_KEYWORDS = [
    "pregnant",
    "pregnancy",
    "breastfeeding",
    "lactating",
    "exclude",
    "excluded",
    "not eligible",
    "ineligible",
    "contraindicated",
    "cannot",
    "no prior",
    "none of",
    "history of",
    "active disease",
    "known allergy",
]


def detect_sections(document_text: str) -> Dict[str, str]:
    """Detect inclusion/exclusion sections in protocol text.

    Args:
        document_text: Raw protocol text.

    Returns:
        Dict mapping section type to section content.
    """
    sections: Dict[str, str] = {}

    inc_match = INCLUSION_HEADER.search(document_text)
    exc_match = EXCLUSION_HEADER.search(document_text)

    if not inc_match and not exc_match:
        inc_match = INLINE_INCLUSION.search(document_text)
        exc_match = INLINE_EXCLUSION.search(document_text)

    if not inc_match and not exc_match:
        return sections

    def _truncate_at_boundary(text: str) -> str:
        boundary = SECTION_END_PATTERNS.search(text)
        return text[: boundary.start()] if boundary else text

    if inc_match and exc_match:
        if inc_match.start() < exc_match.start():
            sections["inclusion"] = _truncate_at_boundary(
                document_text[inc_match.end() : exc_match.start()]
            )
            sections["exclusion"] = _truncate_at_boundary(
                document_text[exc_match.end() :]
            )
        else:
            sections["exclusion"] = _truncate_at_boundary(
                document_text[exc_match.end() : inc_match.start()]
            )
            sections["inclusion"] = _truncate_at_boundary(
                document_text[inc_match.end() :]
            )
    elif inc_match:
        sections["inclusion"] = _truncate_at_boundary(document_text[inc_match.end() :])
    elif exc_match:
        sections["exclusion"] = _truncate_at_boundary(document_text[exc_match.end() :])

    return sections


SECTION_END_PATTERNS = re.compile(
    r"(?:^|\n)\s*(?:"
    r"study\s*design|"
    r"methods?|"
    r"statistical\s*analysis|"
    r"references?|"
    r"procedures?|"
    r"interventions?|"
    r"endpoints?|"
    r"outcome\s*measures?|"
    r"assessments?|"
    r"safety|"
    r"adverse\s*events?|"
    r"bibliography"
    r")\s*:?\s*(?:\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
