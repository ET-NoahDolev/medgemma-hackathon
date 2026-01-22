#!/usr/bin/env bash
# Start MLflow UI with SQLite backend to avoid filesystem backend warnings

set -euo pipefail

# Get the repo root directory (parent of scripts/)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_ROOT"

# Use absolute path to SQLite database
MLFLOW_DB="${REPO_ROOT}/mlflow.db"
MLFLOW_TRACKING_URI="sqlite:///${MLFLOW_DB}"

# Set default artifact root to avoid filesystem backend warnings
# Use a directory in the repo root for artifacts
MLFLOW_ARTIFACT_ROOT="${REPO_ROOT}/mlflow-artifacts"

echo "🚀 Starting MLflow UI..."
echo "   Tracking URI: ${MLFLOW_TRACKING_URI}"
echo "   Database: ${MLFLOW_DB}"
echo "   Artifact Root: ${MLFLOW_ARTIFACT_ROOT}"
echo "   UI: http://localhost:5000"
echo ""

# Ensure artifact directory exists
mkdir -p "${MLFLOW_ARTIFACT_ROOT}"

# Start MLflow UI with the SQLite backend
# Explicitly set default-artifact-root to avoid filesystem backend conflicts
uv run mlflow ui \
    --backend-store-uri "${MLFLOW_TRACKING_URI}" \
    --default-artifact-root "file://${MLFLOW_ARTIFACT_ROOT}" \
    --host 127.0.0.1 \
    --port 5000
