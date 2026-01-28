"""Semantic cache for extraction results."""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from dataclasses import dataclass

from shared.lazy_cache import lazy_singleton

from extraction_service.schemas import ExtractionResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CachedExtraction:
    """Stored semantic cache entry."""

    key_hash: str
    embedding: list[float]
    result: ExtractionResult
    created_at: float


def _read_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid float for {name}: {raw}") from exc


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid integer for {name}: {raw}") from exc


class ExtractionSemanticCache:
    """In-memory semantic cache for extraction results."""

    def __init__(self, similarity_threshold: float, ttl_seconds: int) -> None:
        """Initialize cache with similarity threshold and TTL."""
        self._threshold = similarity_threshold
        self._ttl_seconds = ttl_seconds
        self._items: list[CachedExtraction] = []
        self._lock = threading.Lock()
        self._encoder = self._load_encoder()

    def _load_encoder(self):  # type: ignore[no-untyped-def]
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "Semantic cache requires sentence-transformers installed."
            ) from exc
        return SentenceTransformer("all-MiniLM-L6-v2")

    def _embed(self, text: str) -> list[float]:
        embedding = self._encoder.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def get(self, text: str) -> tuple[ExtractionResult | None, float]:
        """Return cached extraction result and similarity score."""
        if not text.strip():
            return None, 0.0
        query_embedding = self._embed(text)
        now = time.time()
        with self._lock:
            self._items = [
                item
                for item in self._items
                if now - item.created_at <= self._ttl_seconds
            ]
            items = list(self._items)
        best_score = 0.0
        best_result: ExtractionResult | None = None
        for item in items:
            score = _cosine_similarity(query_embedding, item.embedding)
            if score > best_score:
                best_score = score
                best_result = item.result
        if best_score >= self._threshold:
            return best_result, best_score
        return None, best_score

    def set(self, text: str, result: ExtractionResult) -> None:
        """Store an extraction result in the cache."""
        if not text.strip():
            return
        key_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        embedding = self._embed(text)
        entry = CachedExtraction(
            key_hash=key_hash,
            embedding=embedding,
            result=result,
            created_at=time.time(),
        )
        with self._lock:
            self._items.append(entry)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


@lazy_singleton
def get_extraction_cache() -> ExtractionSemanticCache:
    """Return a shared semantic cache for extraction results."""
    similarity_threshold = _read_float_env(
        "EXTRACTION_SEMANTIC_SIMILARITY_THRESHOLD", 0.95
    )
    ttl_seconds = _read_int_env("EXTRACTION_SEMANTIC_CACHE_TTL_SECONDS", 3600)
    return ExtractionSemanticCache(
        similarity_threshold=similarity_threshold, ttl_seconds=ttl_seconds
    )
