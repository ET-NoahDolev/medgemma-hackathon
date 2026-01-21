"""Opt-in integration tests for Vertex AI inference.

These tests are skipped by default because they require:
- a deployed Vertex AI Endpoint
- Application Default Credentials (ADC) configured locally
- network access

Enable with:
  VERTEX_E2E=1 uv run pytest -k vertex_e2e
"""

from __future__ import annotations

import os

import pytest
from langchain_core.messages import HumanMessage

from inference import AgentConfig, create_model_loader


def _required_env_vars_present() -> bool:
    required = ("GCP_PROJECT_ID", "GCP_REGION", "VERTEX_ENDPOINT_ID")
    return all((os.getenv(k) or "").strip() for k in required)


@pytest.mark.integration
def test_vertex_e2e_chat_invoke() -> None:
    """Smoke test: create Vertex model and invoke once.

    This asserts that:
    - `create_model_loader()` can build a Vertex-backed model
    - the endpoint responds to a minimal prompt
    """
    if os.getenv("VERTEX_E2E") != "1":
        pytest.skip("Set VERTEX_E2E=1 to enable Vertex integration tests.")

    if not _required_env_vars_present():
        pytest.skip(
            "Missing required Vertex env vars: GCP_PROJECT_ID, GCP_REGION, "
            "VERTEX_ENDPOINT_ID."
        )

    cfg = AgentConfig(
        backend="vertex",
        gcp_project_id=os.getenv("GCP_PROJECT_ID", "").strip(),
        gcp_region=os.getenv("GCP_REGION", "europe-west4").strip(),
        vertex_endpoint_id=os.getenv("VERTEX_ENDPOINT_ID", "").strip(),
        # Keep this small for cost/speed.
        max_new_tokens=int(os.getenv("VERTEX_E2E_MAX_TOKENS", "32")),
    )

    loader = create_model_loader(cfg)
    model = loader()

    prompt = os.getenv("VERTEX_E2E_PROMPT", "Reply with 'ok' only.")
    response = model.invoke([HumanMessage(content=prompt)])

    content = getattr(response, "content", None)
    assert isinstance(content, str)
    assert content.strip() != ""

