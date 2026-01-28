from __future__ import annotations

import types

import pytest

from inference.vertex_cache import VertexCacheConfig, VertexContextCache


def test_vertex_cache_respects_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
    monkeypatch.setenv("GCP_REGION", "europe-west4")
    monkeypatch.setenv("GEMINI_MODEL_NAME", "gemini-2.5-pro")
    monkeypatch.setenv("VERTEX_CACHE_TTL_SECONDS", "1")

    cache = VertexContextCache(VertexCacheConfig.from_env())

    create_count = {"count": 0}

    class DummyCacheObj:
        def __init__(self, name: str) -> None:
            self.name = name

    class DummyCaches:
        def create(self, **_kwargs: object) -> DummyCacheObj:
            create_count["count"] += 1
            return DummyCacheObj(f"cache-{create_count['count']}")

    class DummyModels:
        def generate_content(self, **_kwargs: object) -> object:
            return types.SimpleNamespace(text="ok")

    class DummyClient:
        caches = DummyCaches()
        models = DummyModels()

    class DummyTypes:
        class CreateCachedContentConfig:
            def __init__(self, **_kwargs: object) -> None:
                return None

        class Content:
            def __init__(self, **_kwargs: object) -> None:
                return None

        class Part:
            def __init__(self, **_kwargs: object) -> None:
                return None

        class GenerateContentConfig:
            def __init__(self, **_kwargs: object) -> None:
                return None

    monkeypatch.setattr(cache, "_get_client", lambda: (DummyClient(), DummyTypes))

    times = [1000.0, 1000.5, 1002.0, 1002.0, 1002.0]

    def _fake_time() -> float:
        return times.pop(0) if times else 1002.0

    monkeypatch.setattr("inference.vertex_cache.time.time", _fake_time)

    name1 = cache.get_or_create_cache("system prompt")
    name2 = cache.get_or_create_cache("system prompt")
    assert name1 == name2
    assert create_count["count"] == 1

    name3 = cache.get_or_create_cache("system prompt")
    assert name3 != name1
    assert create_count["count"] == 2

    response = cache.generate_with_cache("system prompt", "user")
    assert response == "ok"
