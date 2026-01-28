"""Unified ingestion pipeline for extraction and grounding."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, cast

from anyio import to_thread
from extraction_service import pipeline as extraction_pipeline
from extraction_service.tools import extract_triplet
from grounding_service import umls_client
from grounding_service.computed_fields import detect_computed_field
from shared.mlflow_utils import set_trace_metadata

from api_service.storage import Criterion as StorageCriterion
from api_service.storage import Storage

logger = logging.getLogger(__name__)


def _parse_triplet_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _select_primary_triplet(payload: dict[str, Any]) -> dict[str, Any]:
    if "triplets" in payload and isinstance(payload["triplets"], list):
        for item in payload["triplets"]:
            if isinstance(item, dict):
                return item
        return {}
    return payload


def _triplet_from_extracted(item: object) -> dict[str, Any] | None:
    entity = getattr(item, "entity", None)
    relation = getattr(item, "relation", None)
    value = getattr(item, "value", None)
    unit = getattr(item, "unit", None)
    if not any([entity, relation, value, unit]):
        return None
    return {
        "entity": entity,
        "relation": relation,
        "value": value,
        "unit": unit,
    }


async def _extract_triplet(
    text: str,
    session_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    # Set trace metadata before tool invocation
    set_trace_metadata(user_id=user_id, session_id=session_id, run_id=run_id)
    raw: str = await to_thread.run_sync(_run_extract_triplet, text)
    payload = _parse_triplet_payload(raw)
    return _select_primary_triplet(payload)


def _run_extract_triplet(text: str) -> str:
    tool = extract_triplet
    # LangChain @tool expects .invoke(input: dict) mapping param names to values
    if hasattr(tool, "invoke"):
        return cast(Any, tool).invoke({"text": text})
    if hasattr(tool, "run"):
        return cast(Any, tool).run({"text": text})
    extractor = cast(Callable[[str], str], tool)
    return extractor(text)


async def _ground_with_ai(
    text: str,
    criterion_type: str,
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
    result = await agent.ground(text, criterion_type, session_id, user_id, run_id)
    if not result.terms:
        return {}, [], [], None

    # Store all terms as dicts for database storage
    all_terms = []
    snomed_codes = []
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

    # Use first term as primary for backward compatibility
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


async def _build_criterion_payload(
    *,
    text: str,
    criterion_type: str,
    use_ai_grounding: bool,
    umls_api_key: str,
    extracted_triplet: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]], str | None]:
    if extracted_triplet is not None:
        triplet = extracted_triplet
    else:
        triplet = await _extract_triplet(
            text, session_id=session_id, user_id=user_id, run_id=run_id
        )

    computed_as = None
    entity = triplet.get("entity")
    unit = triplet.get("unit")
    if isinstance(entity, str) and entity:
        computed = detect_computed_field(entity)
        if computed:
            computed_as = computed.get("computation")
            if not unit:
                triplet["unit"] = computed.get("output_unit")

    grounding_payload: dict[str, Any] = {}
    snomed_codes: list[str] = []
    grounding_terms: list[dict[str, Any]] = []
    logical_operator: str | None = None
    if use_ai_grounding:
        try:
            grounding_payload, snomed_codes, grounding_terms, logical_operator = (
                await _ground_with_ai(
                    text,
                    criterion_type,
                    session_id=session_id,
                    user_id=user_id,
                    run_id=run_id,
                )
            )
        except Exception as exc:
            logger.warning("AI grounding failed; falling back to baseline: %s", exc)
    if not grounding_payload:
        grounding_payload, snomed_codes = _ground_baseline(text, umls_api_key)
        # Baseline grounding doesn't provide terms or logical operator
        grounding_terms = []
        logical_operator = None

    merged = _merge_fields(
        triplet=triplet,
        grounding=grounding_payload,
        computed_as=computed_as,
    )
    return merged, snomed_codes, grounding_terms, logical_operator


async def ingest_protocol_document_text(
    *,
    protocol_id: str,
    document_text: str,
    storage: Storage,
    umls_api_key: str,
    session_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> list[StorageCriterion]:
    """Extract criteria, ground them, and store results in the database.

    Args:
        protocol_id: Protocol identifier.
        document_text: Document text to extract from.
        storage: Storage instance for persistence.
        umls_api_key: UMLS API key for grounding.
        session_id: Optional session ID for trace grouping.
        user_id: Optional user ID for trace grouping.
        run_id: Optional run ID to group all traces from a single extraction run.
    """
    use_ai_grounding = os.getenv("USE_AI_GROUNDING", "false").lower() == "true"
    logger.info("Ingestion: use_ai_grounding=%s", use_ai_grounding)

    if not hasattr(extraction_pipeline, "extract_criteria_async"):
        raise RuntimeError("Extraction pipeline does not support async extraction.")

    items = await extraction_pipeline.extract_criteria_async(
        document_text, session_id=session_id, user_id=user_id, run_id=run_id
    )
    iterator = iter(items)

    stored: list[StorageCriterion] = []
    for item in iterator:
        payload, snomed_codes, grounding_terms, logical_operator = (
            await _build_criterion_payload(
                text=item.text,
                criterion_type=item.criterion_type,
                use_ai_grounding=use_ai_grounding,
                umls_api_key=umls_api_key,
                extracted_triplet=_triplet_from_extracted(item),
                session_id=session_id,
                user_id=user_id,
                run_id=run_id,
            )
        )
        entity = payload.get("entity")
        stored.append(
            storage.create_criterion_detail(
                protocol_id=protocol_id,
                text=item.text,
                criterion_type=item.criterion_type,
                confidence=item.confidence,
                entity=entity if isinstance(entity, str) else None,
                relation=payload.get("relation"),
                value=payload.get("value"),
                unit=payload.get("unit"),
                umls_concept=payload.get("umls_concept"),
                umls_id=payload.get("umls_id"),
                computed_as=payload.get("computed_as"),
                triplet_confidence=None,
                grounding_confidence=payload.get("grounding_confidence"),
                logical_operator=logical_operator,
                grounding_terms=grounding_terms,
                snomed_codes=snomed_codes,
            )
        )

    return stored
