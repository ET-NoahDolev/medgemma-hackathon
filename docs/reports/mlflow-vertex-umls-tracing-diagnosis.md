# MLflow Vertex / UMLS Tool Call Tracing – Diagnosis

## What you saw

- **Symptom:** Vertex and UMLS tool calls do not appear as spans in MLflow traces.
- **Console (API terminal):**
  - `WARNING mlflow.tracing.fluent: No active trace found. Please create a span using mlflow.start_span or @mlflow.trace before calling mlflow.update_current_trace.`
  - `WARNING mlflow.tracing.fluent: Failed to start span extract_triplet: 'NoneType' object has no attribute 'set_span_type'.`
  - `WARNING mlflow.tracing.fluent: Failed to start span LangGraph: 'NoneType' object has no attribute 'set_span_type'.`

## Root cause

There was **no active MLflow trace** when extraction/grounding ran.

- Protocol ingestion runs in a **background task** (`_run_extraction`). That task had no root trace.
- LangChain/LangGraph **autolog** tries to add spans (e.g. `extract_triplet`, `LangGraph`, tool calls) to the *current* trace. When the current trace is `None`, span creation fails with `'NoneType' object has no attribute 'set_span_type'`, so no Vertex/UMLS (or other) child spans were recorded.

So the issue was not that Vertex/UMLS weren’t called (they were; logs show `Vertex AI endpoint.predict` and `uts-ws.nlm.nih.gov`), but that **tracing had no root trace** for autolog to attach to.

## Fix applied

1. **Root trace in the API**  
   In `api_service/main.py`, the ingestion block in `_run_extraction` is now wrapped in a root span:

   - We use `mlflow.start_span("ingest_protocol")` so there is always an active trace during ingestion.
   - Autolog can then attach child spans (LangGraph, tools, Vertex, UMLS) to this trace.

2. **Trace inspection script**  
   `scripts/inspect_mlflow_traces.py` lists recent traces and their spans so you can confirm what MLflow recorded.

## What to do next

1. **Restart the API** so it runs with the new code (root span).
2. **Upload a protocol again** and trigger extraction (with AI grounding if you want UMLS/Vertex).
3. **Check traces:**
   - **MLflow UI:** Open the experiment (e.g. `medgemma-extraction-YYYYMMDD-HHMMSS`), open a trace, and look for spans under the root (e.g. `ingest_protocol` → LangGraph / tool / LLM spans).
   - **CLI:**  
     `uv run python scripts/inspect_mlflow_traces.py`  
     You should see at least the root span `ingest_protocol`; ideally also child spans for LangGraph, Vertex, and UMLS tool calls.

## If you still only see the root span

- **Context propagation:** Spans must run in the same async/tracing context as the root. We use `MLFLOW_RUN_TRACER_INLINE=true` (default) so the tracer runs in the main async task. If some tool code runs in a thread pool without propagating context, those spans may not show up.
- **Environment:** Ensure `USE_AI_GROUNDING=true` if you expect UMLS and Vertex tool calls from the grounding agent.
- **Logs:** After a run, check the API console for any new MLflow warnings (e.g. “Failed to start span …”). If those disappear, tracing is at least starting spans; if child spans still don’t appear, the next place to look is context propagation (e.g. thread vs async).
