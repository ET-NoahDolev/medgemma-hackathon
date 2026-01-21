"""Opt-in integration tests for Vertex AI inference.

These tests are skipped by default because they require:
- a deployed Vertex AI Endpoint or a Vertex model name
- Application Default Credentials (ADC) configured locally
- network access

Enable with:
  VERTEX_E2E=1 uv run pytest -k vertex_e2e
"""

from __future__ import annotations

import os
import json
import time

import pytest
from langchain_core.messages import HumanMessage

from inference import AgentConfig, create_model_loader


def _required_env_vars_present() -> bool:
    required = ("GCP_PROJECT_ID", "GCP_REGION")
    if not all((os.getenv(k) or "").strip() for k in required):
        return False
    return bool(
        (os.getenv("VERTEX_ENDPOINT_ID") or "").strip()
        or (os.getenv("VERTEX_MODEL_NAME") or "").strip()
    )


def _debug_log(*, hypothesis_id: str, location: str, message: str, data: dict[str, object]) -> None:
    payload = {
        "sessionId": "debug-session",
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(
            "/Users/noahdolevelixir/Code/gemma-hackathon/.cursor/debug.log",
            "a",
            encoding="utf-8",
        ) as log_file:
            log_file.write(json.dumps(payload) + "\n")
    except OSError:
        return


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
            "Missing required Vertex env vars: GCP_PROJECT_ID, GCP_REGION, and "
            "VERTEX_ENDPOINT_ID or VERTEX_MODEL_NAME."
        )

    # Use from_env() to load all config including vertex_endpoint_url
    cfg = AgentConfig.from_env()
    # Override max_new_tokens if specified (keep small for cost/speed)
    max_tokens = int(os.getenv("VERTEX_E2E_MAX_TOKENS", "32"))
    if max_tokens != cfg.max_new_tokens:
        cfg = AgentConfig(
            backend=cfg.backend,
            model_path=cfg.model_path,
            quantization=cfg.quantization,
            max_new_tokens=max_tokens,
            gcp_project_id=cfg.gcp_project_id,
            gcp_region=cfg.gcp_region,
            vertex_endpoint_id=cfg.vertex_endpoint_id,
            vertex_model_name=cfg.vertex_model_name,
            vertex_endpoint_url=cfg.vertex_endpoint_url,
        )

    loader = create_model_loader(cfg)
    model = loader()
    # #region agent log
    _debug_log(
        hypothesis_id="E",
        location="test_vertex_e2e.py:test_vertex_e2e_chat_invoke",
        message="Loaded model instance",
        data={
            "model_type": type(model).__name__,
            "api_endpoint": getattr(model, "api_endpoint", None),
            "model_name": getattr(model, "model_name", None),
            "client_endpoint": getattr(
                getattr(model, "_client", None), "_client_options", None
            )
            and getattr(
                getattr(model, "_client", None)._client_options,
                "api_endpoint",
                None,
            ),
        },
    )
    # #endregion

    prompt = os.getenv("VERTEX_E2E_PROMPT", "Reply with 'ok' only.")
    try:
        response = model.invoke([HumanMessage(content=prompt)])
    except Exception as exc:  # pragma: no cover - debug instrumentation
        # #region agent log
        _debug_log(
            hypothesis_id="E",
            location="test_vertex_e2e.py:test_vertex_e2e_chat_invoke",
            message="Invocation failed",
            data={"error_type": type(exc).__name__, "error": str(exc)},
        )
        # #endregion
        raise

    content = getattr(response, "content", None)
    assert isinstance(content, str)
    assert content.strip() != ""

