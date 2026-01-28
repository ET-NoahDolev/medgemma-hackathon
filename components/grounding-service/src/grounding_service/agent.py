"""SAG (Search-Augmented Generation) pipeline for grounding clinical trial criteria.

This module implements a deterministic 3-step pipeline instead of a ReAct agent:
1. Extract: LLM extracts clinical terms from text (structured output)
2. Search: Python code calls UMLS API for each term (no LLM)
3. Select: LLM selects best codes from search results (structured output)

This approach is faster and more reliable than ReAct for grounding tasks.
"""

import logging
import os
from pathlib import Path
from typing import Any

from shared.mlflow_utils import set_trace_metadata

from grounding_service.schemas import (
    ExtractedTerm,
    GroundingResult,
    TermExtractionResult,
    UmlsCandidate,
)
from grounding_service.semantic_cache import get_grounding_cache
from grounding_service.umls_client import UmlsClient, get_umls_api_key

logger = logging.getLogger(__name__)


class GroundingPipeline:
    """SAG pipeline for grounding clinical trial criteria.

    Uses a deterministic 3-step approach:
    1. Extract clinical terms (LLM, 1 call)
    2. Search UMLS (Python, no LLM)
    3. Select best codes (LLM, 1 call)

    This is faster and more reliable than ReAct for grounding tasks.
    """

    def __init__(self) -> None:
        """Initialize the grounding pipeline."""
        self._extractor: Any | None = None
        self._selector: Any | None = None

    def _get_extractor(self) -> Any:
        """Get or create the term extraction model."""
        if self._extractor is not None:
            return self._extractor

        from inference import create_structured_extractor
        from inference.model_factory import create_gemini_model_loader

        prompts_dir = Path(__file__).parent / "prompts"
        gemini_loader = create_gemini_model_loader()

        self._extractor = create_structured_extractor(
            model_loader=gemini_loader,
            prompts_dir=prompts_dir,
            response_schema=TermExtractionResult,
            system_template="extract_terms_system.j2",
            user_template="extract_terms_user.j2",
        )
        return self._extractor

    def _get_selector(self) -> Any:
        """Get or create the grounding selection model."""
        if self._selector is not None:
            return self._selector

        from inference import create_structured_extractor
        from inference.model_factory import create_gemini_model_loader

        prompts_dir = Path(__file__).parent / "prompts"
        gemini_loader = create_gemini_model_loader()

        self._selector = create_structured_extractor(
            model_loader=gemini_loader,
            prompts_dir=prompts_dir,
            response_schema=GroundingResult,
            system_template="select_grounding_system.j2",
            user_template="select_grounding_user.j2",
        )
        return self._selector

    def _search_umls(
        self, terms: list[ExtractedTerm]
    ) -> dict[str, list[UmlsCandidate]]:
        """Search UMLS for each extracted term.

        Args:
            terms: List of extracted terms to look up.

        Returns:
            Dictionary mapping term strings to UMLS candidates.
        """
        api_key = get_umls_api_key()
        if not api_key:
            logger.warning("No UMLS API key configured")
            return {}

        results: dict[str, list[UmlsCandidate]] = {}

        try:
            with UmlsClient(api_key=api_key) as client:
                for extracted_term in terms:
                    term = extracted_term.term
                    if term in results:
                        continue  # Skip duplicates

                    try:
                        candidates = client.search_snomed(term, limit=3)
                        results[term] = [
                            UmlsCandidate(
                                term=term,
                                snomed_code=c.code,
                                display=c.display,
                                cui=c.cui,
                            )
                            for c in candidates
                        ]
                    except Exception as e:
                        logger.warning("UMLS search failed for '%s': %s", term, e)
                        results[term] = []
        except Exception as e:
            logger.error("UMLS client error: %s", e)

        return results

    async def ground(
        self,
        criterion_text: str,
        criterion_type: str,
        triplet: dict[str, Any] | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        run_id: str | None = None,
    ) -> GroundingResult:
        """Ground a criterion using the 3-step SAG pipeline.

        Args:
            criterion_text: The criterion text to ground.
            criterion_type: Type of criterion ("inclusion" or "exclusion").
            triplet: Optional MedGemma triplet extraction result.
            session_id: Optional session ID for trace grouping.
            user_id: Optional user ID for trace grouping.
            run_id: Optional run ID to group all traces from a single extraction run.

        Returns:
            GroundingResult with SNOMED codes and field mappings.
        """
        set_trace_metadata(user_id=user_id, session_id=session_id, run_id=run_id)

        # Check cache first
        cache_enabled = (
            os.getenv("ENABLE_GROUNDING_SEMANTIC_CACHE", "").lower() == "true"
        )
        if cache_enabled:
            cache = get_grounding_cache()
            cached_result, similarity = cache.get(criterion_text)
            if cached_result is not None:
                logger.debug(
                    "Grounding cache hit (similarity=%.3f) for %s",
                    similarity,
                    criterion_text[:80],
                )
                return cached_result

        # Step 1: Extract clinical terms (LLM call 1)
        logger.debug("Step 1: Extracting terms from: %s", criterion_text[:80])
        extractor = self._get_extractor()
        extraction_result: TermExtractionResult = await extractor(
            {
                "criterion_text": criterion_text,
                "criterion_type": criterion_type,
                "triplet": triplet,
            }
        )

        if not extraction_result.terms:
            logger.debug("No terms extracted, returning empty result")
            return GroundingResult(
                terms=[],
                logical_operator=None,
                reasoning="No clinical terms found to ground.",
            )

        # Step 2: Search UMLS (Python, no LLM)
        term_count = len(extraction_result.terms)
        logger.debug("Step 2: Searching UMLS for %d terms", term_count)
        umls_candidates = self._search_umls(extraction_result.terms)

        # Step 3: Select best codes (LLM call 2)
        logger.debug("Step 3: Selecting best codes")
        selector = self._get_selector()
        result: GroundingResult = await selector(
            {
                "criterion_text": criterion_text,
                "criterion_type": criterion_type,
                "extracted_terms": [t.model_dump() for t in extraction_result.terms],
                "umls_candidates": {
                    term: [c.model_dump() for c in candidates]
                    for term, candidates in umls_candidates.items()
                },
            }
        )

        # Cache result
        if cache_enabled:
            cache = get_grounding_cache()
            cache.set(criterion_text, result)

        return result

    async def ground_batch(
        self,
        items: list[dict[str, Any]],
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        run_id: str | None = None,
    ) -> list[GroundingResult | None]:
        """Ground multiple criteria using the SAG pipeline.

        Args:
            items: List of dicts with keys: criterion_text, criterion_type, triplet.
            session_id: Optional session ID for trace grouping.
            user_id: Optional user ID for trace grouping.
            run_id: Optional run ID to group all traces from a single extraction run.

        Returns:
            List of GroundingResult objects aligned to input order.
        """
        if not items:
            return []

        set_trace_metadata(user_id=user_id, session_id=session_id, run_id=run_id)

        results: list[GroundingResult | None] = []
        for item in items:
            try:
                result = await self.ground(
                    criterion_text=item.get("criterion_text", ""),
                    criterion_type=item.get("criterion_type", "inclusion"),
                    triplet=item.get("triplet"),
                    session_id=session_id,
                    user_id=user_id,
                    run_id=run_id,
                )
                results.append(result)
            except Exception as e:
                logger.warning("Grounding failed for item: %s", e)
                results.append(None)

        return results


# Backward compatibility alias
GroundingAgent = GroundingPipeline

# Singleton instance
_pipeline_instance: GroundingPipeline | None = None


def get_grounding_agent() -> GroundingPipeline:
    """Get or create singleton grounding pipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = GroundingPipeline()
    return _pipeline_instance
