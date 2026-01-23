from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from shared import mlflow_utils
from shared.lazy_cache import lazy_singleton


def test_lazy_singleton_caches_once() -> None:
    calls: list[int] = []

    def _loader() -> dict[str, int]:
        calls.append(1)
        return {"value": 42}

    cached = lazy_singleton(_loader)
    first = cached()
    second = cached()

    assert first is second
    assert calls == [1]


def test_get_mlflow_tracking_uri_uses_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("TEST=1\n")

    monkeypatch.setattr(mlflow_utils, "find_dotenv", lambda: str(env_path))

    uri = mlflow_utils.get_mlflow_tracking_uri()
    assert uri == f"sqlite:///{tmp_path / 'mlflow.db'}"


def test_configure_mlflow_once_sets_tracking(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, list[str]] = {"uri": [], "experiment": [], "autolog": []}

    def _set_tracking_uri(uri: str) -> None:
        calls["uri"].append(uri)

    def _set_experiment(name: str) -> None:
        calls["experiment"].append(name)

    def _autolog(**kwargs: object) -> None:
        calls["autolog"].append("called")

    fake_mlflow = SimpleNamespace(
        set_tracking_uri=_set_tracking_uri,
        set_experiment=_set_experiment,
        langchain=SimpleNamespace(autolog=_autolog),
        langgraph=SimpleNamespace(autolog=_autolog),
    )

    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)
    monkeypatch.setattr(mlflow_utils, "get_mlflow_tracking_uri", lambda: "sqlite:///tmp/mlflow.db")

    mlflow_utils.configure_mlflow_once("medgemma-extraction")

    assert calls["uri"] == ["sqlite:///tmp/mlflow.db"]
    assert calls["experiment"] == ["medgemma-extraction"]
    assert calls["autolog"] == ["called", "called"]
