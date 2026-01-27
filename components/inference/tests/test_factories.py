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

    cfg = AgentConfig(
        backend="vertex",
        gcp_project_id="p",
        gcp_region="europe-west4",
        vertex_endpoint_id="",
        vertex_model_name="",
    )
    with pytest.raises(ValueError, match="VERTEX_ENDPOINT_ID or VERTEX_MODEL_NAME"):
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
    sys.modules.pop("langchain_google_genai", None)
    sys.modules.pop("langchain_google_vertexai", None)

    loader = create_model_loader(cfg)
    assert callable(loader)
    assert "vertexai" not in sys.modules
    assert "langchain_google_vertexai" not in sys.modules


def test_vertex_loader_initializes_and_builds_resource_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Full offline test: env selects vertex backend; loader initializes vertexai and
    # constructs ModelGardenChatModel with endpoint resource name.
    monkeypatch.setenv("MODEL_BACKEND", "vertex")
    monkeypatch.setenv("GCP_PROJECT_ID", "my-project")
    monkeypatch.setenv("GCP_REGION", "europe-west4")
    monkeypatch.setenv("VERTEX_ENDPOINT_ID", "987654321")
    monkeypatch.delenv("VERTEX_MODEL_NAME", raising=False)

    init_args: tuple[str, str] | None = None

    def _init(*, project: str, location: str) -> None:
        nonlocal init_args
        init_args = (project, location)

    class _MockEndpoint:
        """Mock aiplatform.Endpoint for testing."""

        def __init__(self, resource_name: str) -> None:
            self.resource_name = resource_name

        def predict(
            self, instances: list[dict[str, Any]], parameters: dict[str, Any]
        ) -> Any:  # noqa: ANN401
            class _MockResponse:
                predictions = ['{"test": "response"}']
            return _MockResponse()

    import sys
    import types

    monkeypatch.setitem(sys.modules, "vertexai", types.SimpleNamespace(init=_init))
    monkeypatch.setitem(
        sys.modules,
        "google.cloud.aiplatform",
        types.SimpleNamespace(Endpoint=_MockEndpoint),
    )

    loader = create_model_loader()
    model = loader()
    assert model is not None

    assert init_args == ("my-project", "europe-west4")
    # Verify ModelGardenChatModel properties
    assert hasattr(model, "endpoint_resource_name")
    assert model.endpoint_resource_name == (
        "projects/my-project/locations/europe-west4/endpoints/987654321"
    )
    assert model.project == "my-project"
    assert model.location == "europe-west4"
    # max_output_tokens comes from MEDGEMMA_MAX_TOKENS env var (defaults to 2048)
    assert model.max_output_tokens == 2048


def test_vertex_loader_uses_genai_model_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_BACKEND", "vertex")
    monkeypatch.setenv("GCP_PROJECT_ID", "my-project")
    monkeypatch.setenv("GCP_REGION", "europe-west4")
    monkeypatch.setenv("VERTEX_MODEL_NAME", "gemini-1.5-pro")
    monkeypatch.delenv("VERTEX_ENDPOINT_ID", raising=False)

    init_args: tuple[str, str] | None = None
    chat_args: tuple[str, str, str, bool, int] | None = None

    def _init(*, project: str, location: str) -> None:
        nonlocal init_args
        init_args = (project, location)

    class _ChatGoogleGenerativeAI:
        def __init__(
            self,
            *,
            model: str,
            project: str,
            location: str,
            vertexai: bool,
            max_output_tokens: int,
        ) -> None:
            nonlocal chat_args
            chat_args = (
                model,
                project,
                location,
                vertexai,
                max_output_tokens,
            )

    import sys
    import types

    monkeypatch.setitem(sys.modules, "vertexai", types.SimpleNamespace(init=_init))
    monkeypatch.setitem(
        sys.modules,
        "langchain_google_genai",
        types.SimpleNamespace(ChatGoogleGenerativeAI=_ChatGoogleGenerativeAI),
    )

    loader = create_model_loader()
    model = loader()
    assert model is not None

    assert init_args == ("my-project", "europe-west4")
    # max_output_tokens comes from MEDGEMMA_MAX_TOKENS env var (defaults to 2048)
    assert chat_args == ("gemini-1.5-pro", "my-project", "europe-west4", True, 2048)


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
        async def ainvoke(
            self, _payload: object, *, config: object | None = None
        ) -> dict[str, object]:
            return {"structured_response": {"ok": True}}

    def dummy_model_loader() -> object:
        return object()

    # Monkeypatch langchain.agents.create_agent to return DummyAgent
    def _create_agent(**_kw: Any) -> DummyAgent:
        return DummyAgent()
    monkeypatch.setattr("langchain.agents.create_agent", _create_agent)

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

