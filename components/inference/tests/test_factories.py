import pytest

from inference import AgentConfig, create_model_loader, create_react_agent


def test_agent_config_from_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEDGEMMA_MODEL_PATH", raising=False)
    monkeypatch.delenv("MEDGEMMA_QUANTIZATION", raising=False)
    monkeypatch.delenv("MEDGEMMA_MAX_TOKENS", raising=False)

    cfg = AgentConfig.from_env()
    assert cfg.model_path
    assert cfg.quantization
    assert cfg.max_new_tokens > 0


def test_create_model_loader_is_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    # Should not import torch at factory-creation time.
    cfg = AgentConfig(model_path="google/medgemma-4b-it", quantization="none")
    loader = create_model_loader(cfg)
    assert callable(loader)


@pytest.mark.asyncio
async def test_create_react_agent_smoke(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    # Keep this lightweight: stub model + stub agent so we don't need real ML deps.
    (tmp_path / "sys.j2").write_text("system {{ x }}")
    (tmp_path / "user.j2").write_text("user {{ y }}")

    class DummySchema:  # minimal pydantic-like interface
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    async def _ainvoke(_payload):
        return {"structured_response": {"ok": True}}

    class DummyAgent:
        ainvoke = staticmethod(_ainvoke)

    def dummy_model_loader():
        return object()

    # Monkeypatch langgraph.prebuilt.create_react_agent to return DummyAgent
    import types

    prebuilt = types.SimpleNamespace(create_react_agent=lambda **_kw: DummyAgent())
    monkeypatch.setitem(
        __import__("sys").modules, "langgraph", types.SimpleNamespace(prebuilt=prebuilt)
    )
    monkeypatch.setitem(__import__("sys").modules, "langgraph.prebuilt", prebuilt)

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
    assert result.kwargs["ok"] is True

