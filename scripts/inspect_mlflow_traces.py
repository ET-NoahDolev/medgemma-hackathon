#!/usr/bin/env python3
"""Inspect recent MLflow traces and their spans (for diagnosing Vertex/UMLS tool calls)."""

import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))
load_dotenv(find_dotenv())


def _tracking_uri() -> str:
    env_path = find_dotenv()
    root = Path(env_path).parent.absolute() if env_path else Path.cwd()
    return f"sqlite:///{root / 'mlflow.db'}"


def main() -> None:
    import mlflow

    mlflow.set_tracking_uri(_tracking_uri())
    print("=" * 60)
    print("Recent MLflow traces (spans = tool/LLM steps)")
    print("=" * 60)
    print(f"Tracking URI: {_tracking_uri()}\n")

    # Search traces; return_type="list" for Trace objects (MLflow 2.21.1+)
    kwargs = {"max_results": 10, "order_by": ["timestamp_ms DESC"]}
    if hasattr(mlflow, "search_traces"):
        try:
            raw = mlflow.search_traces(return_type="list", **kwargs)
        except TypeError:
            raw = mlflow.search_traces(**kwargs)
    else:
        from mlflow.tracking import MlflowClient
        client = MlflowClient()
        exps = client.search_experiments()
        exp_ids = [e.experiment_id for e in exps]
        raw = client.search_traces(experiment_ids=exp_ids, max_results=10)
    # Normalize: DataFrame has "trace" column; otherwise list of Trace
    if hasattr(raw, "columns") and "trace" in getattr(raw, "columns", []):
        traces = list(raw["trace"])
    elif isinstance(raw, list):
        traces = raw
    else:
        traces = list(raw) if raw is not None else []
    if not traces:
        print("No traces found. Upload a protocol and run extraction, then run this again.")
        return

    for i, trace in enumerate(traces):
        info = getattr(trace, "info", None)
        trace_id = info.request_id if info and hasattr(info, "request_id") else (info.trace_id if info else None) or str(trace)[:30]
        print(f"Trace {i + 1}: {trace_id}")
        if info:
            print(f"  Experiment ID: {getattr(info, 'experiment_id', '?')}")
            ts = getattr(info, "timestamp_ms", None) or getattr(info, "request_time", None)
            if ts:
                print(f"  Timestamp: {ts}")
            tags = getattr(info, "tags", None) or {}
            trace_name = tags.get("mlflow.traceName", "")
            if trace_name:
                print(f"  Name: {trace_name}")
        data = getattr(trace, "data", None)
        spans = list(getattr(data, "spans", []) or getattr(trace, "spans", []) or [])
        print(f"  Spans ({len(spans)}):")
        for span in spans:
            name = getattr(span, "name", "?")
            span_type = getattr(span, "span_type", None) or "?"
            parent_id = getattr(span, "parent_id", None)
            print(f"    - {name!r} (type={span_type}, parent_id={parent_id})")
        print()
    print("=" * 60)
    print("If you see only 'ingest_protocol' and no LangGraph/Vertex/UMLS spans,")
    print("ensure the API was restarted after the root-trace fix and re-upload a protocol.")
    print("=" * 60)


if __name__ == "__main__":
    main()
