from __future__ import annotations

from pathlib import Path

import pytest

from grounding_service import umls_client


@pytest.fixture(autouse=True)
def isolate_umls_cache_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache_root = tmp_path / "umls_cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UMLS_CACHE_DIR", str(cache_root))


@pytest.fixture()
def umls() -> umls_client.UmlsClient:
    client = umls_client.UmlsClient(api_key="test-key")
    yield client
    client.close()
