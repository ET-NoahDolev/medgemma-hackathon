# MLflow Logging Troubleshooting Guide

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
DEBUG: MLflow: Logged prompts for agent invocation
DEBUG: MLflow: Logged structured response
```

**For Grounding:**
```
INFO: Grounding: use_ai=True, AGENT_AVAILABLE=True
```

**If you see warnings:**
```
WARNING: MLflow prompt logging failed (non-fatal): ...
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

4. Look for runs with:
   - Parameters: `system_template`, `user_template`
   - Artifacts: `system_prompt.txt`, `user_prompt.txt`, `response.json`, `raw_result.json`

### 5. Test Agent Invocation

**Test Extraction:**
1. Upload a protocol via API
2. Trigger extraction
3. Check logs for MLflow messages
4. Check MLflow UI for new runs

**Test Grounding:**
1. Set `USE_AI_GROUNDING=true`
2. Extract criteria first
3. Ground a criterion
4. Check logs and MLflow UI

## Common Issues

### No Runs Appearing in MLflow

**Possible causes:**
1. Environment variables not set (agents not running)
2. MLflow not installed
3. Database file permissions issue
4. Tracking URI mismatch

**Solution:**
- Run diagnostic script
- Check application logs for warnings
- Verify database file exists and is writable

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

3. **Verify Tracking URI:**
   ```python
   import mlflow
   print(f"Tracking URI: {mlflow.get_tracking_uri()}")
   ```

4. **Test Direct Logging:**
   ```python
   import mlflow
   mlflow.set_tracking_uri("sqlite:///path/to/mlflow.db")
   mlflow.set_experiment("test")
   with mlflow.start_run():
       mlflow.log_param("test", "value")
   ```
