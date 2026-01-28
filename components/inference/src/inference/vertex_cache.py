"""Vertex AI context caching helpers for Gemini models."""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VertexCacheConfig:
    """Configuration for Vertex context caching."""

    project_id: str
    region: str
    model_name: str

    @classmethod
    def from_env(cls) -> "VertexCacheConfig":
        """Load cache config from environment variables."""
        project_id = (os.getenv("GCP_PROJECT_ID") or "").strip()
        region = (os.getenv("GCP_REGION") or "europe-west4").strip()
        model_name = (os.getenv("GEMINI_MODEL_NAME") or "gemini-2.5-pro").strip()
        if not project_id:
            raise ValueError("GCP_PROJECT_ID is required for Vertex context cache.")
        return cls(project_id=project_id, region=region, model_name=model_name)


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid integer for {name}: {raw}") from exc


class VertexContextCache:
    """Create and reuse Vertex cached content for repeated system prompts."""

    def __init__(self, config: VertexCacheConfig) -> None:
        """Initialize the cache with Vertex configuration."""
        self._config = config
        self._cache: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        self._ttl_seconds = _read_int_env("VERTEX_CACHE_TTL_SECONDS", 3600)

    def _get_client(self) -> tuple[Any, Any]:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "Vertex context caching requires google-genai installed."
            ) from exc
        client = genai.Client(
            vertexai=True,
            project=self._config.project_id,
            location=self._config.region,
            http_options=types.HttpOptions(api_version="v1"),
        )
        return client, types

    def _model_path(self) -> str:
        return (
            f"projects/{self._config.project_id}/locations/"
            f"{self._config.region}/publishers/google/models/"
            f"{self._config.model_name}"
        )

    def get_or_create_cache(self, system_prompt: str) -> str:
        """Return cached content name for the given system prompt."""
        cache_key = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
        with self._lock:
            cached_entry = self._cache.get(cache_key)
        if cached_entry:
            cache_name, created_at = cached_entry
            if time.time() - created_at <= self._ttl_seconds:
                return cache_name
            with self._lock:
                self._cache.pop(cache_key, None)

        client, types = self._get_client()
        cache = client.caches.create(
            model=self._model_path(),
            config=types.CreateCachedContentConfig(
                display_name=f"system-prompt-{cache_key[:12]}",
                system_instruction=system_prompt,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text="")],
                    )
                ],
            ),
        )
        with self._lock:
            self._cache[cache_key] = (cache.name, time.time())
        return cache.name

    def generate_with_cache(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a response using cached system prompt context."""
        client, types = self._get_client()
        cache_name = self.get_or_create_cache(system_prompt)
        response = client.models.generate_content(
            model=self._model_path(),
            contents=[
                types.Content(role="user", parts=[types.Part(text=user_prompt)])
            ],
            config=types.GenerateContentConfig(cached_content=cache_name),
        )
        return response.text or ""


_CACHE: VertexContextCache | None = None


def get_vertex_cache() -> VertexContextCache:
    """Return a singleton VertexContextCache instance."""
    global _CACHE
    if _CACHE is None:
        config = VertexCacheConfig.from_env()
        _CACHE = VertexContextCache(config)
    return _CACHE
