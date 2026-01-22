"""Tests for AgentConfig."""


from inference.config import AgentConfig


def test_supports_tools_local_backend() -> None:
    """Test that local backend does not support tools."""
    cfg = AgentConfig(backend="local")
    assert cfg.supports_tools is False


def test_supports_tools_vertex_with_endpoint_only() -> None:
    """Test that vertex backend with endpoint only does not support tools."""
    cfg = AgentConfig(
        backend="vertex",
        gcp_project_id="test-project",
        gcp_region="us-central1",
        vertex_endpoint_id="endpoint-123",
        vertex_model_name="",
    )
    assert cfg.supports_tools is False


def test_supports_tools_vertex_with_model_name() -> None:
    """Test that vertex backend with model name supports tools."""
    cfg = AgentConfig(
        backend="vertex",
        gcp_project_id="test-project",
        gcp_region="us-central1",
        vertex_endpoint_id="",
        vertex_model_name="gemini-2.5-pro",
    )
    assert cfg.supports_tools is True


def test_supports_tools_vertex_with_both_prioritizes_model_name() -> None:
    """Test that vertex backend with both endpoint and model name supports tools."""
    cfg = AgentConfig(
        backend="vertex",
        gcp_project_id="test-project",
        gcp_region="us-central1",
        vertex_endpoint_id="endpoint-123",
        vertex_model_name="gemini-2.5-pro",
    )
    assert cfg.supports_tools is True
