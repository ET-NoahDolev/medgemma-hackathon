#!/usr/bin/env python3
"""Diagnostic script to check MLflow configuration and logging."""

import logging
import os
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

# Load environment variables from .env file
load_dotenv(find_dotenv())

print("=" * 60)
print("MLflow Configuration Diagnostic")
print("=" * 60)
print()

# Check 1: Environment variables
print("1. Environment Variables:")
print(f"   USE_MODEL_EXTRACTION: {os.getenv('USE_MODEL_EXTRACTION', 'NOT SET (defaults to true)')}")
print(f"   USE_AI_GROUNDING: {os.getenv('USE_AI_GROUNDING', 'NOT SET (defaults to false)')}")
print(f"   LOG_LEVEL: {os.getenv('LOG_LEVEL', 'NOT SET (defaults to INFO)')}")
print(f"   MLFLOW_TRACKING_URI: {os.getenv('MLFLOW_TRACKING_URI', 'NOT SET')}")
print()

# Check 2: MLflow installation
print("2. MLflow Installation:")
try:
    import mlflow
    print(f"   ✓ MLflow version: {mlflow.__version__}")
except ImportError:
    print("   ✗ MLflow not installed")
    sys.exit(1)
print()

# Check 3: Tracking URI
print("3. Tracking URI Configuration:")
try:
    from dotenv import find_dotenv
    
    env_path = find_dotenv()
    if not env_path:
        print("   ✗ .env file not found")
    else:
        repo_root = Path(env_path).parent.absolute()
        db_path = repo_root / "mlflow.db"
        tracking_uri = f"sqlite:///{db_path}"
        print(f"   Repo root: {repo_root}")
        print(f"   Database path: {db_path}")
        print(f"   Database exists: {db_path.exists()}")
        print(f"   Tracking URI: {tracking_uri}")
        
        # Try to set and verify
        mlflow.set_tracking_uri(tracking_uri)
        actual_uri = mlflow.get_tracking_uri()
        print(f"   MLflow tracking URI: {actual_uri}")
        if actual_uri != tracking_uri:
            print("   ⚠ WARNING: Tracking URI mismatch!")
except Exception as e:
    print(f"   ✗ Error: {e}")
print()

# Check 4: Experiments
print("4. Experiment Configuration:")
experiments = [
    ("medgemma-extraction", "API Service"),
    ("medgemma-grounding", "Grounding Service"),
    ("medgemma-inference", "Inference/Agent Factory"),
]

for exp_name, service in experiments:
    try:
        mlflow.set_experiment(exp_name)
        exp = mlflow.get_experiment_by_name(exp_name)
        if exp:
            print(f"   ✓ {exp_name} ({service}): ID={exp.experiment_id}")
        else:
            print(f"   ⚠ {exp_name} ({service}): Will be created on first run")
    except Exception as e:
        print(f"   ✗ {exp_name} ({service}): Error - {e}")
print()

# Check 5: Test logging
print("5. Test MLflow Logging:")
try:
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("medgemma-inference")
    with mlflow.start_run(run_name="diagnostic_test"):
        mlflow.log_param("test_param", "test_value")
        mlflow.log_metric("test_metric", 1.0)
        mlflow.log_text("test text", artifact_file="test.txt")
        active_run = mlflow.active_run()
        run_id = active_run.info.run_id if active_run else "unknown"
    print(f"   ✓ Successfully logged test run: {run_id}")
    
    # Try to retrieve it
    client = mlflow.tracking.MlflowClient()
    run = client.get_run(run_id)
    print("   ✓ Successfully retrieved run from database")
    print(f"   Run ID: {run.info.run_id}")
    print(f"   Status: {run.info.status}")
except Exception as e:
    print(f"   ✗ Error during test logging: {e}")
    import traceback
    traceback.print_exc()
print()

# Check 6: Agent factory MLflow availability
print("6. Agent Factory MLflow Check:")
print("   Agent factory does not initialize MLflow; use shared.mlflow_utils.")
print()

# Check 7: Logging level
print("7. Logging Configuration:")

# Configure logging based on LOG_LEVEL environment variable
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
try:
    log_level = getattr(logging, log_level_str, logging.INFO)
except AttributeError:
    log_level = logging.INFO

# Configure logging
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)

root_logger = logging.getLogger()
print(f"   LOG_LEVEL env var: {log_level_str}")
print(f"   Configured log level: {logging.getLevelName(log_level)}")
print(f"   Root logger level: {logging.getLevelName(root_logger.level)}")
print(f"   Debug logging enabled: {root_logger.level <= logging.DEBUG}")
print()

print("=" * 60)
print("Diagnostic Complete")
print("=" * 60)
