#!/usr/bin/env bash
set -euo pipefail

#
# GCP setup script for Vertex AI + GCS.
#
# This script is designed to be idempotent. It enables required APIs and creates
# a GCS bucket for datasets/models used by Vertex tuning and inference.
#
# Usage:
#   ./scripts/setup_gcp.sh
#   GCP_PROJECT_ID=my-project GCP_REGION=us-central1 ./scripts/setup_gcp.sh
#   ./scripts/setup_gcp.sh --dry-run
#

DRY_RUN=false
DEPLOY_MODEL=false
WRITE_ENV_TEMPLATE=true
WRITE_CONFIG=true

usage() {
  cat <<'EOF'
Usage: ./scripts/setup_gcp.sh [options]

Options:
  --dry-run        Print commands without executing them
  --deploy-model   (Optional) Print instructions for model deployment
  --no-env         Do not generate .env.vertex template file
  --no-config      Do not write scripts/gcp_config.json
  -h, --help       Show this help

Environment variables:
  GCP_PROJECT_ID      GCP project ID (required; will prompt if missing)
  GCP_REGION          GCP region (default: europe-west4)
  GCS_BUCKET_NAME     Bucket name (default: ${GCP_PROJECT_ID}-medgemma)
EOF
}

run() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "+ $*"
    return 0
  fi
  "$@"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

ensure_gcloud_auth() {
  # `gcloud auth list` exits 0 even if no accounts; parse output instead.
  local accounts
  accounts="$(gcloud auth list --format='value(account)' 2>/dev/null || true)"
  if [[ -z "${accounts}" ]]; then
    echo "No gcloud account is authenticated. Run:" >&2
    echo "  gcloud auth login" >&2
    echo "  gcloud auth application-default login" >&2
    exit 1
  fi
}

prompt_project_id() {
  local current="${GCP_PROJECT_ID:-}"
  if [[ -n "${current}" ]]; then
    return 0
  fi
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "GCP_PROJECT_ID is required (set it via env var)."
    exit 1
  fi
  read -r -p "Enter GCP project id (GCP_PROJECT_ID): " current
  current="${current//[[:space:]]/}"
  if [[ -z "${current}" ]]; then
    echo "GCP_PROJECT_ID is required." >&2
    exit 1
  fi
  export GCP_PROJECT_ID="${current}"
}

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) DRY_RUN=true ;;
      --deploy-model) DEPLOY_MODEL=true ;;
      --no-env) WRITE_ENV_TEMPLATE=false ;;
      --no-config) WRITE_CONFIG=false ;;
      -h|--help) usage; exit 0 ;;
      *)
        echo "Unknown option: $1" >&2
        usage
        exit 1
        ;;
    esac
    shift
  done

  require_cmd gcloud
  require_cmd gsutil

  ensure_gcloud_auth
  prompt_project_id

  local region="${GCP_REGION:-europe-west4}"
  local bucket_name="${GCS_BUCKET_NAME:-${GCP_PROJECT_ID}-medgemma}"
  bucket_name="${bucket_name#gs://}"
  bucket_name="${bucket_name%/}"

  run gcloud config set project "${GCP_PROJECT_ID}"

  echo "Enabling required APIs..."
  run gcloud services enable aiplatform.googleapis.com
  run gcloud services enable storage-api.googleapis.com
  run gcloud services enable artifactregistry.googleapis.com

  echo "Creating/ensuring GCS bucket: gs://${bucket_name} (${region})"
  if run gsutil ls -b "gs://${bucket_name}" >/dev/null 2>&1; then
    echo "Bucket already exists."
  else
    run gsutil mb -p "${GCP_PROJECT_ID}" -l "${region}" "gs://${bucket_name}"
  fi

  # Create placeholder objects to establish common prefixes.
  # gsutil will error if the object already exists; ignore failures.
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "+ gsutil cp /dev/null gs://${bucket_name}/training/.keep"
    echo "+ gsutil cp /dev/null gs://${bucket_name}/models/.keep"
  else
    gsutil cp /dev/null "gs://${bucket_name}/training/.keep" >/dev/null 2>&1 || true
    gsutil cp /dev/null "gs://${bucket_name}/models/.keep" >/dev/null 2>&1 || true
  fi

  if [[ "${WRITE_ENV_TEMPLATE}" == "true" ]]; then
    local repo_root
    repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    
    # Try to detect existing Vertex endpoints
    local endpoint_id=""
    if [[ "${DRY_RUN}" != "true" ]]; then
      # Look for endpoints with "medgemma" in the name (case-insensitive)
      # Suppress errors in case API isn't enabled or no endpoints exist yet
      local endpoints
      endpoints=$(gcloud ai endpoints list \
        --region="${region}" \
        --format="value(name)" \
        --filter="displayName~(?i)medgemma" \
        2>/dev/null || echo "")
      
      if [[ -n "${endpoints}" ]]; then
        # Take the first one found and extract just the endpoint ID
        endpoint_id=$(echo "${endpoints}" | head -n1 | sed 's|.*/endpoints/||' || echo "")
        if [[ -n "${endpoint_id}" ]]; then
          echo "Found existing Vertex endpoint: ${endpoint_id}"
        fi
      fi
    fi
    
    cat > "${repo_root}/.env.vertex" <<EOF
# Vertex AI Inference Configuration
# Source this file or export these variables before running services:
#   source .env.vertex
#   export \$(cat .env.vertex | xargs)

# Backend selection: "local" or "vertex"
MODEL_BACKEND=vertex

# GCP Project Configuration
GCP_PROJECT_ID=${GCP_PROJECT_ID}
GCP_REGION=${region}

# Vertex AI Endpoint (required for MODEL_BACKEND=vertex)
# Get this from: gcloud ai endpoints list --region=${region}
# Or from Vertex AI Console -> Endpoints
VERTEX_ENDPOINT_ID=${endpoint_id}

# GCS Bucket for training data and model artifacts
GCS_BUCKET=gs://${bucket_name}

# Optional: Training backend selection ("local" or "vertex")
# TRAINING_BACKEND=vertex

# Optional: Vertex E2E test configuration (for integration tests)
# VERTEX_E2E=1
# VERTEX_E2E_MAX_TOKENS=32
# VERTEX_E2E_PROMPT="Reply with 'ok' only."
EOF
    if [[ -z "${endpoint_id}" ]]; then
      echo "Wrote ${repo_root}/.env.vertex"
      echo "  ⚠️  VERTEX_ENDPOINT_ID is empty - fill it after deploying your model."
      echo "     List endpoints: gcloud ai endpoints list --region=${region}"
    else
      echo "Wrote ${repo_root}/.env.vertex (with detected endpoint ID)"
    fi
  fi

  if [[ "${WRITE_CONFIG}" == "true" ]]; then
    local repo_root
    repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    cat > "${repo_root}/scripts/gcp_config.json" <<EOF
{
  "project_id": "${GCP_PROJECT_ID}",
  "region": "${region}",
  "gcs_bucket": "gs://${bucket_name}"
}
EOF
    echo "Wrote ${repo_root}/scripts/gcp_config.json"
  fi

  if [[ "${DEPLOY_MODEL}" == "true" ]]; then
    echo
    echo "Next: deploy MedGemma on Vertex AI."
    echo "- Option A (recommended): Vertex AI Model Garden -> search 'MedGemma' -> Deploy"
    echo "- Option B: custom container / vLLM deployment (see instructions/vertex_pamphlet.md)"
    echo
    echo "After deployment, update .env.vertex with your endpoint ID:"
    echo "  VERTEX_ENDPOINT_ID=\$(gcloud ai endpoints list --region=${region} --format='value(name)' --filter='displayName~medgemma' | head -n1 | sed 's|.*/endpoints/||')"
    echo "  sed -i '' \"s/^VERTEX_ENDPOINT_ID=.*/VERTEX_ENDPOINT_ID=\${VERTEX_ENDPOINT_ID}/\" .env.vertex"
    echo
    echo "Or manually edit .env.vertex and set VERTEX_ENDPOINT_ID"
  fi

  echo
  echo "✅ GCP setup complete!"
  if [[ "${WRITE_ENV_TEMPLATE}" == "true" ]]; then
    echo
    echo "To use Vertex AI backend, source the environment file:"
    echo "  source .env.vertex"
    echo
    echo "Or export variables manually:"
    echo "  export \$(grep -v '^#' .env.vertex | xargs)"
    echo
    echo "Then run your services - they will automatically use Vertex AI."
  fi
}

main "$@"

