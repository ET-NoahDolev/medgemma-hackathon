from __future__ import annotations

import pytest

from grounding_service.schemas import GroundedTerm, GroundingResult
from grounding_service.semantic_cache import get_grounding_cache


def test_semantic_cache_env_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROUNDING_SEMANTIC_SIMILARITY_THRESHOLD", "0.9")
    monkeypatch.setenv("GROUNDING_SEMANTIC_CACHE_TTL_SECONDS", "3600")

    class DummyVector:
        def tolist(self) -> list[float]:
            return [1.0, 0.0]

    class DummyEncoder:
        def encode(self, _text: str, convert_to_numpy: bool = True) -> DummyVector:
            return DummyVector()

    monkeypatch.setattr(
        "grounding_service.semantic_cache.GroundingSemanticCache._load_encoder",
        lambda self: DummyEncoder(),
    )
    get_grounding_cache.cache_clear()
    cache = get_grounding_cache()

    result = GroundingResult(
        terms=[
            GroundedTerm(
                snippet="Age >= 18",
                raw_criterion_text="Age >= 18",
                criterion_type="inclusion",
                snomed_code="123",
                relation=">=",
                value="18",
                confidence=0.9,
            )
        ],
        reasoning="ok",
    )

    cache.set("Age >= 18", result)
    cached, score = cache.get("Age >= 18")
    assert cached == result
    assert score >= 0.9
