from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TypedDict

import pytest

try:
    import mlflow
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - optional dependency surface
    mlflow = None  # type: ignore[assignment]


class _State(TypedDict):
    counter: int


def _write_debug_log(hypothesis_id: str, message: str, data: dict[str, object]) -> None:
    # region agent log
    try:
        with open(
            "/Users/noahdolevelixir/Code/gemma-hackathon/.cursor/debug.log",
            "a",
            encoding="utf-8",
        ) as log_file:
            log_file.write(
                json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": "trace-smoke",
                        "hypothesisId": hypothesis_id,
                        "location": "test_mlflow_tracing_smoke.py",
                        "message": message,
                        "data": data,
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # endregion


@pytest.mark.asyncio
async def test_mlflow_langgraph_smoke_tracing(tmp_path: Path) -> None:
    if mlflow is None:
        pytest.skip("mlflow or langgraph not available")

    tracking_uri = f"sqlite:///{tmp_path / 'mlflow_tracing.db'}"
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("debug-mlflow-tracing")

    logger = logging.getLogger("mlflow.tracing.fluent")
    logger.setLevel(logging.DEBUG)
    log_records: list[str] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            log_records.append(record.getMessage())
            _write_debug_log(
                "H5",
                "mlflow tracing log record",
                {"level": record.levelname, "message": record.getMessage()},
            )

    handler = _Handler()
    logger.addHandler(handler)

    try:
        mlflow.langchain.autolog(run_tracer_inline=True)
        if hasattr(mlflow, "langgraph"):
            mlflow.langgraph.autolog()
        _write_debug_log(
            "H1",
            "autolog configured for smoke test",
            {"tracking_uri": tracking_uri, "log_count": len(log_records)},
        )

        graph = StateGraph(_State)

        async def _step(state: _State) -> _State:
            return {"counter": state["counter"] + 1}

        graph.add_node("step", _step)
        graph.add_edge(START, "step")
        graph.add_edge("step", END)

        app = graph.compile()
        result = await app.ainvoke({"counter": 0})
        _write_debug_log("H4", "langgraph invoke completed", {"result": result})
    finally:
        logger.removeHandler(handler)
