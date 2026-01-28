"""Unified ingestion pipeline for extraction and grounding."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Iterable, Iterator, Sequence, cast

from extraction_service.pdf_chunker import chunk_pdf, should_chunk_pdf
from extraction_service.pdf_extractor import extract_criteria_from_pdf
from extraction_service.tools import extract_triplets_batch
from grounding_service import umls_client
from grounding_service.computed_fields import detect_computed_field
from grounding_service.schemas import GroundingResult

from api_service.storage import Criterion as StorageCriterion
from api_service.storage import Storage

logger = logging.getLogger(__name__)


def _normalize_criterion_text(text: str) -> str:
    cleaned = " ".join(text.split())
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)
    return cleaned.rstrip(".;:").strip()


def _chunked(items: Sequence[Any], size: int) -> Iterator[list[Any]]:
    if size <= 0:
        raise ValueError("Chunk size must be positive.")
    for idx in range(0, len(items), size):
        yield list(items[idx : idx + size])


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _deduplicate_snippets(items: Iterable[object]) -> list[object]:
    deduped: list[object] = []
    seen: set[str] = set()
    for item in items:
        text = getattr(item, "text", None)
        if not isinstance(text, str):
            continue
        normalized = _normalize_criterion_text(text)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(item)
    return deduped


def _coerce_triplet_batch(
    payload: object, expected: int
) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        logger.warning("Triplet batch payload is not a list.")
        return [{} for _ in range(expected)]
    triplets: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            triplets.append(item)
        else:
            triplets.append({})
    if len(triplets) < expected:
        triplets.extend([{} for _ in range(expected - len(triplets))])
    if len(triplets) > expected:
        triplets = triplets[:expected]
    return triplets


def _extract_triplets_batch(criteria_texts: list[str]) -> list[dict[str, Any]]:
    try:
        payload = extract_triplets_batch(criteria_texts)
    except ValueError as exc:
        logger.warning("MedGemma batch triplet extraction failed: %s", exc)
        return [{} for _ in criteria_texts]
    return _coerce_triplet_batch(payload, len(criteria_texts))


async def _extract_pdf_criteria_items(
    pdf_bytes: bytes,
    *,
    session_id: str | None,
    user_id: str | None,
    run_id: str | None,
) -> list[object]:
    items: list[object] = []
    if should_chunk_pdf(pdf_bytes):
        for chunk in chunk_pdf(pdf_bytes):
            result = await extract_criteria_from_pdf(
                pdf_bytes=chunk.data,
                session_id=session_id,
                user_id=user_id,
                run_id=run_id,
            )
            items.extend(result.criteria)
    else:
        result = await extract_criteria_from_pdf(
            pdf_bytes=pdf_bytes,
            session_id=session_id,
            user_id=user_id,
            run_id=run_id,
        )
        items.extend(result.criteria)
    return _deduplicate_snippets(items)


def _apply_computed_field(
    triplet: dict[str, Any]
) -> tuple[dict[str, Any], str | None]:
    computed_as = None
    entity = triplet.get("entity")
    unit = triplet.get("unit")
    if isinstance(entity, str) and entity:
        computed = detect_computed_field(entity)
        if computed:
            computed_as = computed.get("computation")
            if not unit:
                triplet = {**triplet, "unit": computed.get("output_unit")}
    return triplet, computed_as


def _coerce_grounding_result(
    result: GroundingResult,
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]], str | None]:
    if not result.terms:
        return {}, [], [], None

    all_terms: list[dict[str, Any]] = []
    snomed_codes: list[str] = []
    for term in result.terms:
        term_dict = {
            "umls_concept": term.umls_concept,
            "umls_id": term.umls_id,
            "snomed_code": term.snomed_code,
            "relation": term.relation,
            "value": term.value,
            "unit": term.unit,
            "computed_as": term.computed_as,
            "grounding_confidence": term.confidence,
            "relation_confidence": term.relation_confidence,
            "value_confidence": term.value_confidence,
            "umls_confidence": term.umls_confidence,
            "snippet": term.snippet,
        }
        all_terms.append(term_dict)
        if term.snomed_code:
            snomed_codes.append(term.snomed_code)

    term = result.terms[0]
    primary_dict = {
        "umls_concept": term.umls_concept,
        "umls_id": term.umls_id,
        "snomed_code": term.snomed_code,
        "relation": term.relation,
        "value": term.value,
        "unit": term.unit,
        "computed_as": term.computed_as,
        "grounding_confidence": term.confidence,
        "relation_confidence": term.relation_confidence,
        "value_confidence": term.value_confidence,
        "umls_confidence": term.umls_confidence,
    }

    return primary_dict, snomed_codes, all_terms, result.logical_operator


async def _ground_with_ai(
    text: str,
    criterion_type: str,
    *,
    triplet: dict[str, Any] | None,
    session_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]], str | None]:
    """Ground criterion with AI and return all terms.

    Returns:
        Tuple of (primary_term_dict, snomed_codes, all_terms_dicts, logical_operator)
    """
    try:
        from grounding_service.agent import get_grounding_agent
    except ImportError:  # pragma: no cover
        return {}, [], [], None

    agent = get_grounding_agent()
    # Pass session/user/run IDs to grounding agent which will set trace metadata
    result = await agent.ground(
        text,
        criterion_type,
        triplet=triplet,
        session_id=session_id,
        user_id=user_id,
        run_id=run_id,
    )
    return _coerce_grounding_result(result)


async def _ground_with_ai_batch(
    *,
    items: list[dict[str, Any]],
    session_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> list[GroundingResult | None]:
    try:
        from grounding_service.agent import get_grounding_agent
    except ImportError:  # pragma: no cover
        return [None for _ in items]

    agent = get_grounding_agent()
    try:
        return await agent.ground_batch(
            items,
            session_id=session_id,
            user_id=user_id,
            run_id=run_id,
        )
    except Exception as exc:
        logger.warning("AI batch grounding failed: %s", exc)
        return [None for _ in items]


def _ground_baseline(text: str, api_key: str) -> tuple[dict[str, Any], list[str]]:
    with umls_client.UmlsClient(api_key=api_key) as client:
        candidates = client.search_snomed(text)
        snomed_codes = [candidate.code for candidate in candidates]
        field_mappings = umls_client.propose_field_mapping(text)
        mapping = field_mappings[0] if field_mappings else None
        return (
            {
                "relation": mapping.relation if mapping else None,
                "value": mapping.value if mapping else None,
                "unit": None,
                "grounding_confidence": mapping.confidence if mapping else None,
            },
            snomed_codes,
        )


def _merge_fields(
    *,
    triplet: dict[str, Any],
    grounding: dict[str, Any],
    computed_as: str | None,
) -> dict[str, Any]:
    relation = triplet.get("relation") or grounding.get("relation")
    value = triplet.get("value") or grounding.get("value")
    unit = triplet.get("unit") or grounding.get("unit")
    if grounding.get("computed_as") and not computed_as:
        computed_as = grounding.get("computed_as")

    return {
        "entity": triplet.get("entity"),
        "relation": relation,
        "value": value,
        "unit": unit,
        "umls_concept": grounding.get("umls_concept"),
        "umls_id": grounding.get("umls_id"),
        "computed_as": computed_as,
        "grounding_confidence": grounding.get("grounding_confidence"),
    }


async def ingest_protocol_from_pdf(
    *,
    protocol_id: str,
    pdf_bytes: bytes,
    storage: Storage,
    umls_api_key: str,
    session_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> list[StorageCriterion]:
    """Extract, ground, and store criteria from a PDF using Gemini + MedGemma.

    Args:
        protocol_id: Protocol identifier.
        pdf_bytes: PDF content to analyze.
        storage: Storage instance for persistence.
        umls_api_key: UMLS API key for grounding.
        session_id: Optional session ID for trace grouping.
        user_id: Optional user ID for trace grouping.
        run_id: Optional run ID to group all traces from a single extraction run.
    """
    use_ai_grounding = os.getenv("USE_AI_GROUNDING", "false").lower() == "true"
    logger.info("Ingestion: use_ai_grounding=%s", use_ai_grounding)

    deduped_items = await _extract_pdf_criteria_items(
        pdf_bytes,
        session_id=session_id,
        user_id=user_id,
        run_id=run_id,
    )
    if not deduped_items:
        return []

    batch_size = _read_int_env("MEDGEMMA_BATCH_SIZE", 3)
    stored: list[StorageCriterion] = []

    for batch in _chunked(deduped_items, batch_size):
        texts = [cast(str, getattr(item, "text", "")) for item in batch]
        triplets = _extract_triplets_batch(texts)
        batch_payload: list[dict[str, Any]] = []
        for item, triplet in zip(batch, triplets, strict=False):
            text = cast(str, getattr(item, "text", ""))
            criterion_type = cast(str, getattr(item, "criterion_type", ""))
            batch_payload.append(
                {
                    "criterion_text": text,
                    "criterion_type": criterion_type,
                    "triplet": triplet if isinstance(triplet, dict) else None,
                }
            )

        if use_ai_grounding:
            batch_groundings = await _ground_with_ai_batch(
                items=batch_payload,
                session_id=session_id,
                user_id=user_id,
                run_id=run_id,
            )
        else:
            batch_groundings = [None for _ in batch_payload]

        for idx, (item, triplet) in enumerate(zip(batch, triplets, strict=False)):
            text = cast(str, getattr(item, "text", ""))
            criterion_type = cast(str, getattr(item, "criterion_type", ""))
            confidence = float(getattr(item, "confidence", 0.0))

            triplet, computed_as = _apply_computed_field(triplet)
            batch_result = (
                batch_groundings[idx] if idx < len(batch_groundings) else None
            )
            if batch_result is not None and batch_result.terms:
                grounding_payload, snomed_codes, grounding_terms, logical_operator = (
                    _coerce_grounding_result(batch_result)
                )
            else:
                grounding_payload, snomed_codes = _ground_baseline(text, umls_api_key)
                grounding_terms = []
                logical_operator = None

            merged = _merge_fields(
                triplet=triplet,
                grounding=grounding_payload,
                computed_as=computed_as,
            )

            stored.append(
                storage.create_criterion_detail(
                    protocol_id=protocol_id,
                    text=text,
                    criterion_type=criterion_type,
                    confidence=confidence,
                    entity=(
                        merged.get("entity")
                        if isinstance(merged.get("entity"), str)
                        else None
                    ),
                    relation=merged.get("relation"),
                    value=merged.get("value"),
                    unit=merged.get("unit"),
                    umls_concept=merged.get("umls_concept"),
                    umls_id=merged.get("umls_id"),
                    computed_as=merged.get("computed_as"),
                    triplet_confidence=None,
                    grounding_confidence=merged.get("grounding_confidence"),
                    logical_operator=logical_operator,
                    grounding_terms=grounding_terms,
                    snomed_codes=snomed_codes,
                )
            )

    return stored
