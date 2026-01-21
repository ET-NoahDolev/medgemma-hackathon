from pathlib import Path
from typing import Any

import pytest

from inference import AgentConfig, create_model_loader, create_react_agent


def test_agent_config_from_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODEL_BACKEND", raising=False)
    monkeypatch.delenv("MEDGEMMA_BACKEND", raising=False)
    monkeypatch.delenv("MEDGEMMA_MODEL_PATH", raising=False)
    monkeypatch.delenv("MEDGEMMA_QUANTIZATION", raising=False)
    monkeypatch.delenv("MEDGEMMA_MAX_TOKENS", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("GCP_REGION", raising=False)
    monkeypatch.delenv("VERTEX_ENDPOINT_ID", raising=False)

    cfg = AgentConfig.from_env()
    assert cfg.backend in {"local", "vertex"}
    assert cfg.model_path
    assert cfg.quantization
    assert cfg.max_new_tokens > 0


def test_create_model_loader_is_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    # Should not import torch at factory-creation time.
    cfg = AgentConfig(model_path="google/medgemma-4b-it", quantization="none")
    loader = create_model_loader(cfg)
    assert callable(loader)


def test_create_model_loader_vertex_requires_env() -> None:
    cfg = AgentConfig(
        backend="vertex",
        gcp_project_id="",
        gcp_region="europe-west4",
        vertex_endpoint_id="123",
    )
    with pytest.raises(ValueError, match="GCP_PROJECT_ID"):
        create_model_loader(cfg)


def test_vertex_loader_is_lazy_on_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    # Creating the loader should not import vertex dependencies.
    monkeypatch.delenv("MODEL_BACKEND", raising=False)
    monkeypatch.delenv("MEDGEMMA_BACKEND", raising=False)

    cfg = AgentConfig(
        backend="vertex",
        gcp_project_id="p",
        gcp_region="r",
        vertex_endpoint_id="123",
    )

    import sys

    sys.modules.pop("vertexai", None)
    sys.modules.pop("langchain_google_vertexai", None)

    loader = create_model_loader(cfg)
    assert callable(loader)
    assert "vertexai" not in sys.modules
    assert "langchain_google_vertexai" not in sys.modules


def test_vertex_loader_initializes_and_builds_resource_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Full offline test: env selects vertex backend; loader initializes vertexai and
    # constructs ChatVertexAI with endpoint resource name.
    monkeypatch.setenv("MODEL_BACKEND", "vertex")
    monkeypatch.setenv("GCP_PROJECT_ID", "my-project")
    monkeypatch.setenv("GCP_REGION", "europe-west4")
    monkeypatch.setenv("VERTEX_ENDPOINT_ID", "987654321")

    init_args: tuple[str, str] | None = None
    chat_args: tuple[str, int] | None = None

    def _init(*, project: str, location: str) -> None:
        nonlocal init_args
        init_args = (project, location)

    class _ChatVertexAI:
        def __init__(self, *, model_name: str, max_output_tokens: int) -> None:
            nonlocal chat_args
            chat_args = (model_name, max_output_tokens)

    import sys
    import types

    monkeypatch.setitem(sys.modules, "vertexai", types.SimpleNamespace(init=_init))
    monkeypatch.setitem(
        sys.modules,
        "langchain_google_vertexai",
        types.SimpleNamespace(ChatVertexAI=_ChatVertexAI),
    )

    loader = create_model_loader()
    model = loader()
    assert model is not None

    assert init_args == ("my-project", "europe-west4")
    assert chat_args is not None
    model_name, max_tokens = chat_args
    assert max_tokens == 512
    assert model_name == (
        "projects/my-project/locations/europe-west4/endpoints/987654321"
    )


@pytest.mark.asyncio
async def test_create_react_agent_smoke(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Keep this lightweight: stub model + stub agent so we don't need real ML deps.
    (tmp_path / "sys.j2").write_text("system {{ x }}")
    (tmp_path / "user.j2").write_text("user {{ y }}")

    from pydantic import BaseModel

    class DummySchema(BaseModel):
        ok: bool = False

    class DummyAgent:
        async def ainvoke(self, _payload: object) -> dict[str, object]:
            return {"structured_response": {"ok": True}}

    def dummy_model_loader() -> object:
        return object()

    # Monkeypatch langgraph.prebuilt.create_react_agent to return DummyAgent
    import sys
    import types

    def _create_react_agent(**_kw: Any) -> DummyAgent:
        return DummyAgent()

    prebuilt = types.SimpleNamespace(create_react_agent=_create_react_agent)
    monkeypatch.setitem(
        sys.modules, "langgraph", types.SimpleNamespace(prebuilt=prebuilt)
    )
    monkeypatch.setitem(sys.modules, "langgraph.prebuilt", prebuilt)

    invoke = create_react_agent(
        model_loader=dummy_model_loader,
        prompts_dir=tmp_path,
        tools=[],
        response_schema=DummySchema,
        system_template="sys.j2",
        user_template="user.j2",
    )
    result = await invoke({"x": "a", "y": "b"})
    assert isinstance(result, DummySchema)
    assert result.ok is True

