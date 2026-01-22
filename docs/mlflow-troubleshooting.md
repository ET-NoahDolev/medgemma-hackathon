# MLflow Logging Troubleshooting Guide

## Overview

This project uses **MLflow Tracing** for LLM observability, which provides automatic instrumentation of LangChain and LangGraph calls. The system uses a hybrid approach:

- **MLflow Traces**: For LLM/agent invocations (automatic via autologging)
- **MLflow Runs**: For high-level extraction tracking (manual)

## MLflow Tracing vs Runs

### Traces (Recommended for LLM Observability)
- **Automatic**: LangChain/LangGraph calls are automatically traced
- **Detailed**: Captures token usage, latency, and execution flow
- **Better Visualization**: Shows step-by-step agent execution in MLflow UI
- **OpenTelemetry Compatible**: Integrates with observability stacks

### Runs (Used for High-Level Tracking)
- **Manual**: Explicitly started for extraction workflows
- **Summary Metrics**: Tracks overall extraction statistics
- **Experiment Organization**: Groups related extractions together

## Root Cause Analysis

### Issues Identified

1. **Silent Failures**
   - MLflow errors were logged at `DEBUG` level, making them invisible at default log levels
   - **Fix**: Changed to `WARNING` level with `exc_info=True` for full stack traces

2. **Experiment Context Mismatch**
   - Agent factory was setting experiment to "medgemma-inference" at module import
   - API service sets experiment to "medgemma-extraction" when starting runs
   - This caused nested runs to fail or log to wrong experiment
   - **Fix**: Removed experiment setting from agent factory module init; let calling service control experiment

3. **Missing Environment Variables**
   - `USE_MODEL_EXTRACTION` defaults to `true` but might be explicitly set to `false`
   - `USE_AI_GROUNDING` defaults to `false` and must be explicitly set to `true`
   - If these aren't set correctly, agents won't run and nothing gets logged
   - **Fix**: Added logging to show when agents are/aren't being used

4. **Module Initialization Errors**
   - MLflow initialization errors in agent factory were silently swallowed
   - **Fix**: Added proper exception handling with warnings

5. **Tracking URI Not Persisted**
   - Agent factory might lose tracking URI context between calls
   - **Fix**: Re-set tracking URI before each logging operation

6. **Missing MLflow in Runtime Dependencies**
   - MLflow was only in dev dependencies, causing silent failures in production
   - **Fix**: Added MLflow to runtime dependencies for all services

## Verification Steps

### 1. Run Diagnostic Script

```bash
uv run python scripts/diagnose_mlflow.py
```

This will check:
- Environment variables
- MLflow installation
- Tracking URI configuration
- Database file existence
- Experiment setup
- Test logging functionality

### 2. Check Environment Variables

Ensure these are set correctly:

```bash
# For extraction (defaults to true if not set)
export USE_MODEL_EXTRACTION=true

# For grounding (must be explicitly set)
export USE_AI_GROUNDING=true
```

### 3. Check Application Logs

Look for these log messages:

**For Extraction:**
```
INFO: Extraction: use_model=True, MLflow active=True
INFO: MLflow: Started run <run_id> for protocol <protocol_id>
INFO: MLflow LangChain autologging enabled
INFO: MLflow LangGraph autologging enabled
```

**For Grounding:**
```
INFO: Grounding: use_ai=True, AGENT_AVAILABLE=True
```

**If you see warnings:**
```
WARNING: MLflow not available - tracing disabled. Install mlflow for observability.
WARNING: MLflow prompt logging failed (non-fatal): ...
WARNING: Failed to enable LangChain autologging: ...
```

This indicates MLflow is trying to log but failing. Check the full stack trace.

### 4. Verify MLflow UI

1. Start MLflow UI:
   ```bash
   ./scripts/start-mlflow-ui.sh
   ```

2. Open http://localhost:5000

3. Check for experiments:
   - `medgemma-extraction` (for extraction runs)
   - `medgemma-grounding` (for grounding runs)
   - `medgemma-inference` (for standalone agent runs)

4. **View Traces** (for LLM observability):
   - Navigate to the "Traces" tab in MLflow UI
   - Look for traces from agent invocations
   - Traces show detailed execution flow, token usage, and latency
   - Traces are automatically created by autologging

5. **View Runs** (for high-level tracking):
   - Look for runs with:
     - Parameters: `system_template`, `user_template`
     - Artifacts: `system_prompt.txt`, `user_prompt.txt`, `response.json`, `raw_result.json`
   - Runs show overall extraction statistics

### 5. Test Agent Invocation

**Test Extraction:**
1. Upload a protocol via API
2. Trigger extraction
3. Check logs for MLflow messages (autologging enabled, traces created)
4. Check MLflow UI for:
   - **Traces**: Detailed LLM call traces with token usage
   - **Runs**: High-level extraction tracking

**Test Grounding:**
1. Set `USE_AI_GROUNDING=true`
2. Extract criteria first
3. Ground a criterion
4. Check logs and MLflow UI for traces and runs

## Common Issues

### No Traces or Runs Appearing in MLflow

**Possible causes:**
1. MLflow not installed in runtime dependencies
2. Environment variables not set (agents not running)
3. Database file permissions issue
4. Tracking URI mismatch
5. Autologging not enabled

**Solution:**
- Verify MLflow is in runtime dependencies (not just dev)
- Run diagnostic script: `uv run python scripts/diagnose_mlflow.py`
- Check application logs for warnings about MLflow availability
- Verify database file exists and is writable
- Check logs for "MLflow LangChain autologging enabled" message

### Runs Appear But No Artifacts

**Possible causes:**
1. Artifact root not configured
2. Permission issues with artifact directory
3. Silent failures during artifact logging

**Solution:**
- Check MLflow UI script sets `--default-artifact-root`
- Verify artifact directory exists and is writable
- Check logs for artifact logging errors

### Nested Runs Not Working

**Possible causes:**
1. Experiment context mismatch
2. Parent run ended before nested run starts
3. MLflow version compatibility

**Solution:**
- Ensure parent run is active when nested run starts
- Check experiment names match
- Verify MLflow version >= 3.8.1

### Traces Not Appearing

**Possible causes:**
1. Autologging not enabled
2. LangChain/LangGraph calls not being made
3. MLflow tracing API not available in version

**Solution:**
- Check logs for "MLflow LangChain autologging enabled"
- Verify agents are actually being invoked (check `USE_MODEL_EXTRACTION` and `USE_AI_GROUNDING`)
- Ensure MLflow version >= 3.8.1 for tracing support
- Check MLflow UI "Traces" tab (not just "Runs" tab)

### Token Usage Not Tracked

**Possible causes:**
1. Autologging not capturing token metrics
2. Model provider doesn't expose token counts
3. MLflow version doesn't support token tracking

**Solution:**
- Verify autologging is enabled
- Check trace details in MLflow UI for token metrics
- Some model providers may not expose token counts

## Configuration

### Environment Variables

- `MLFLOW_TRACING_ASYNC`: Enable async tracing (default: `true`)
- `MLFLOW_TRACING_SAMPLING_RATIO`: Sampling ratio for high-throughput (0.0-1.0)
- `USE_MODEL_EXTRACTION`: Enable model-based extraction (default: `true`)
- `USE_AI_GROUNDING`: Enable AI-based grounding (default: `false`)

### Tracing Configuration

Tracing is configured in `components/inference/src/inference/mlflow_config.py`. This module:
- Enables async logging for production
- Configures sampling if needed
- Provides utilities for trace context and tags

## Debugging Tips

1. **Enable Debug Logging:**
   ```python
   import logging
   logging.getLogger().setLevel(logging.DEBUG)
   ```

2. **Check Active Run:**
   ```python
   import mlflow
   run = mlflow.active_run()
   print(f"Active run: {run}")
   ```

3. **Check Active Trace:**
   ```python
   import mlflow
   trace = mlflow.tracing.get_active_trace()
   print(f"Active trace: {trace}")
   ```

4. **Verify Tracking URI:**
   ```python
   import mlflow
   print(f"Tracking URI: {mlflow.get_tracking_uri()}")
   ```

5. **Test Direct Logging:**
   ```python
   import mlflow
   mlflow.set_tracking_uri("sqlite:///path/to/mlflow.db")
   mlflow.set_experiment("test")
   with mlflow.start_run():
       mlflow.log_param("test", "value")
   ```

6. **Test Tracing:**
   ```python
   import mlflow
   mlflow.set_tracking_uri("sqlite:///path/to/mlflow.db")
   with mlflow.start_trace(name="test_trace"):
       # Your code here
       pass
   ```
