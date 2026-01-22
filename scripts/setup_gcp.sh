#!/usr/bin/env bash
set -euo pipefail

#
# GCP setup script for Vertex AI + GCS.
#
# This script is designed to be idempotent. It enables required APIs and creates
# a GCS bucket for datasets/models used by Vertex tuning and inference.
#
# SECURITY NOTE: This script writes infrastructure identifiers (project IDs,
# endpoint IDs, bucket names) to local files (.env, gcp_config.json).
# These files are gitignored and should NEVER be committed. The script itself
# contains NO secrets and is safe to commit to public repositories.
#
# Usage:
#   ./scripts/setup_gcp.sh
#   GCP_PROJECT_ID=my-project GCP_REGION=us-central1 ./scripts/setup_gcp.sh
#   ./scripts/setup_gcp.sh --dry-run
#

DRY_RUN=false
WRITE_ENV_TEMPLATE=true
WRITE_CONFIG=true

usage() {
  cat <<'EOF'
Usage: ./scripts/setup_gcp.sh [options]

Options:
  --dry-run        Print commands without executing them
  --no-env         Do not update .env with Vertex settings
  --no-config      Do not write scripts/gcp_config.json
  -h, --help       Show this help

Environment variables:
  GCP_PROJECT_ID          GCP project ID (required; will prompt if missing)
  GCP_REGION              GCP region (default: europe-west4)
  GCS_BUCKET_NAME         Bucket name (default: ${GCP_PROJECT_ID}-medgemma)
  VERTEX_PUBLISHER_MODEL  Model Garden model (default: google/medgemma@medgemma-1.5-4b-it)
  VERTEX_MACHINE_TYPE     Machine type (default: g2-standard-12)
  VERTEX_ACCEL_TYPE       Accelerator type (default: NVIDIA_L4)
  VERTEX_ACCEL_COUNT      Accelerator count (default: 1)
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

update_env_var() {
  local env_file="$1"
  local key="$2"
  local value="$3"

  if [[ ! -f "${env_file}" ]]; then
    echo "${key}=${value}" > "${env_file}"
    return 0
  fi

  if grep -q "^${key}=" "${env_file}"; then
    local tmp_file
    tmp_file="$(mktemp)"
    awk -v k="${key}" -v v="${value}" '
      $0 ~ "^" k "=" { print k "=" v; updated=1; next }
      { print }
      END { if (!updated) print k "=" v }
    ' "${env_file}" > "${tmp_file}"
    mv "${tmp_file}" "${env_file}"
  else
    echo "${key}=${value}" >> "${env_file}"
  fi
}

ensure_gcloud_auth() {
  # `gcloud auth list` exits 0 even if no accounts; parse output instead.
  local accounts
  accounts="$(gcloud auth list --format='value(account)' 2>/dev/null || true)"
  if [[ -z "${accounts}" ]]; then
    echo "No gcloud account is authenticated." >&2
    echo "" >&2
    echo "Please authenticate using SSO:" >&2
    echo "  gcloud auth login --sso" >&2
    echo "" >&2
    echo "Then set up Application Default Credentials:" >&2
    echo "  gcloud auth application-default login" >&2
    exit 1
  fi
  
  # Check if Application Default Credentials are set up
  if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    echo "⚠️  Application Default Credentials not configured." >&2
    echo "   Run: gcloud auth application-default login" >&2
    echo "" >&2
    echo "   Continuing anyway (some operations may fail)..." >&2
    echo "" >&2
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

  # Set env_path for later use
  local repo_root
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  repo_root="$(cd "${script_dir}/.." && pwd)"
  local env_path="${repo_root}/.env"

  # Note: VERTEX_ENDPOINT_ID will be set later after deployment check/creation
  # We'll update .env after we determine the endpoint ID

  if [[ "${WRITE_CONFIG}" == "true" ]]; then
    cat > "${repo_root}/scripts/gcp_config.json" <<EOF
{
  "project_id": "${GCP_PROJECT_ID}",
  "region": "${region}",
  "gcs_bucket": "gs://${bucket_name}"
}
EOF
    echo "✅ Wrote scripts/gcp_config.json"
    echo "  ⚠️  SECURITY: This file contains infrastructure identifiers and is gitignored."
    echo "     Do not commit this file or share it publicly."
  fi

  # Deploy MedGemma from Model Garden
  echo
  echo "Checking for existing MedGemma deployment..."

  local publisher_model="${VERTEX_PUBLISHER_MODEL:-google/medgemma@medgemma-1.5-4b-it}"
  local machine_type="${VERTEX_MACHINE_TYPE:-g2-standard-12}"
  local accelerator_type="${VERTEX_ACCEL_TYPE:-NVIDIA_L4}"
  local accelerator_count="${VERTEX_ACCEL_COUNT:-1}"
  local medgemma_endpoint_display_name="medgemma-1-5-4b-it-endpoint"

  # Initialize endpoint variables
  local endpoint_id=""
  local endpoint_resource_name=""

  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "+ Checking for existing endpoint: ${medgemma_endpoint_display_name}"
    echo "+ uv run python ... # Deploy ${publisher_model} to Vertex AI (if needed)"
  else
    # Check ONCE for endpoint with exact display name (this is the only endpoint we care about)
    endpoint_resource_name=$(gcloud ai endpoints list \
      --region="${region}" \
      --filter="displayName=${medgemma_endpoint_display_name}" \
      --format="value(name)" \
      2>/dev/null | head -n1 || true)

    if [[ -n "${endpoint_resource_name}" ]]; then
      # Endpoint exists - check if it has deployed models
      local deployed_count
      deployed_count=$(gcloud ai endpoints describe "${endpoint_resource_name}" \
        --region="${region}" \
        --format="value(deployedModels.id)" \
        2>/dev/null | wc -w | tr -d ' ' || echo "0")
      
      endpoint_id=$(echo "${endpoint_resource_name}" | sed 's|.*/endpoints/||')
      
      if [[ "${deployed_count}" -gt 0 ]]; then
        echo "✅ Found existing MedGemma deployment."
        echo "   Endpoint ID: ${endpoint_id}"
        echo "   Display Name: ${medgemma_endpoint_display_name}"
        echo "   Deployed Models: ${deployed_count}"
        echo "   ✅ Skipping deployment to avoid duplicates."
      else
        echo "⚠️  Found endpoint '${medgemma_endpoint_display_name}' but it has no deployed models."
        echo "   ⚠️  The model.deploy() method with use_dedicated_endpoint=True creates new endpoints."
        echo "   ⚠️  Skipping automatic deployment to avoid creating duplicate endpoints."
        echo "   💡 You can deploy manually from Model Garden:"
        echo "      https://console.cloud.google.com/vertex-ai/model-garden?project=${GCP_PROJECT_ID}"
        echo "   💡 Or delete the empty endpoint and re-run this script."
      fi
    else
      # No endpoint exists - proceed with deployment
      echo "No existing endpoint found. Deploying MedGemma 1.5 4B to Vertex AI..."
      echo "This will take 10-15 minutes..."
      echo ""

      # Run Python deployment script with better error handling
      echo "Initializing Vertex AI..."
      local deploy_result
      local deploy_exit_code=0
      
      deploy_result=$(uv run python - <<PYEOF 2>&1 || deploy_exit_code=$?
import sys
import json

try:
    import vertexai
    from vertexai import model_garden
except ImportError as e:
    print(json.dumps({"error": f"Missing dependency: {e}. Run: pip install google-cloud-aiplatform vertexai"}), file=sys.stderr)
    sys.exit(1)

try:
    print("Initializing Vertex AI client...", file=sys.stderr)
    vertexai.init(project="${GCP_PROJECT_ID}", location="${region}")

    print(f"Opening model: ${publisher_model}", file=sys.stderr)
    model = model_garden.OpenModel("${publisher_model}")
    
    # Get recommended deployment options from the model (optional - for logging)
    print("Querying recommended deployment configuration...", file=sys.stderr)
    try:
        deploy_options = model.list_deploy_options()
        if deploy_options and len(deploy_options) > 0:
            recommended = deploy_options[0]
            machine_spec = recommended.get("machine_spec", {})
            rec_machine = machine_spec.get("machine_type", "unknown")
            rec_accel = machine_spec.get("accelerator_type", "unknown")
            rec_count = machine_spec.get("accelerator_count", "unknown")
            print(f"Recommended config: {rec_machine} with {rec_accel} x{rec_count}", file=sys.stderr)
    except Exception as e:
        print(f"Could not get recommended options ({e})", file=sys.stderr)
    
    # Use provided/default machine spec
    final_machine_type = "${machine_type}"
    final_accel_type = "${accelerator_type}"
    final_accel_count = ${accelerator_count}
    print(f"Using machine spec: {final_machine_type} with {final_accel_type} x{final_accel_count}", file=sys.stderr)
    
    print("Starting deployment (this will take 10-15 minutes)...", file=sys.stderr)
    print("You can monitor progress in the GCP Console.", file=sys.stderr)
    
    # Note: Don't pass serving_container_image_uri for Model Garden models.
    # The Model Garden API automatically uses the correct container.
    endpoint = model.deploy(
        accept_eula=True,
        machine_type=final_machine_type,
        accelerator_type=final_accel_type,
        accelerator_count=final_accel_count,
        endpoint_display_name="${medgemma_endpoint_display_name}",
        model_display_name="medgemma-1-5-4b-it",
        use_dedicated_endpoint=True,
        reservation_affinity_type="NO_RESERVATION",
    )

    # Extract endpoint resource name
    endpoint_name = endpoint.resource_name
    print(json.dumps({"endpoint_resource_name": endpoint_name}))

except Exception as e:
    import traceback
    error_details = {
        "error": str(e),
        "type": type(e).__name__,
        "traceback": traceback.format_exc()
    }
    print(json.dumps(error_details), file=sys.stderr)
    print(json.dumps(error_details))
    sys.exit(1)
PYEOF
      )

      if [[ "${deploy_exit_code}" -ne 0 ]] || echo "${deploy_result}" | grep -q '"error"'; then
        local error_msg
        error_msg=$(echo "${deploy_result}" | uv run python -c "import sys,json; d=json.load(sys.stdin); print(d.get('error', 'Unknown error'))" 2>/dev/null || echo "${deploy_result}")
        echo ""
        echo "❌ Deployment failed: ${error_msg}"
        echo ""
        echo "Full error output:"
        echo "${deploy_result}"
        echo ""
        echo "You can deploy manually from Model Garden:"
        echo "   https://console.cloud.google.com/vertex-ai/model-garden?project=${GCP_PROJECT_ID}"
        echo ""
      else
        endpoint_resource_name=$(echo "${deploy_result}" | uv run python -c "import sys,json; print(json.load(sys.stdin).get('endpoint_resource_name',''))" 2>/dev/null || echo "")
        if [[ -z "${endpoint_resource_name}" ]]; then
          echo "⚠️  Deployment may have started, but couldn't extract endpoint ID."
          echo "   Check the GCP Console for deployment status."
          echo "   https://console.cloud.google.com/vertex-ai/endpoints?project=${GCP_PROJECT_ID}"
        else
          endpoint_id=$(echo "${endpoint_resource_name}" | sed 's|.*/endpoints/||')
          echo ""
          echo "✅ MedGemma deployed successfully!"
          echo "   Endpoint ID: ${endpoint_id}"
          echo "   Resource: ${endpoint_resource_name}"
        fi
      fi
    fi

    # Update .env with endpoint ID (if we have one)
    if [[ -n "${endpoint_id}" ]]; then
      # Ensure .env file exists with basic structure
      if [[ ! -f "${env_path}" ]]; then
        cat > "${env_path}" <<EOF
# Local development environment settings.
# NOTE: This file is gitignored and should never be committed.

# UMLS API key (required for grounding service)
# UMLS_API_KEY=your_key_here

# Backend selection: "local" or "vertex"
MODEL_BACKEND=vertex

# GCP Project Configuration
GCP_PROJECT_ID=${GCP_PROJECT_ID}
GCP_REGION=${region}

# Vertex AI Endpoint (for MODEL_BACKEND=vertex with deployed MedGemma)
# Use this when you've deployed MedGemma from Model Garden to an endpoint.
VERTEX_ENDPOINT_ID=${endpoint_id}

# Alternative: Vertex Model Name (for MODEL_BACKEND=vertex without endpoint)
# Use this for calling Vertex AI models directly (e.g., gemini-pro).
# If VERTEX_MODEL_NAME is set, VERTEX_ENDPOINT_ID is ignored.
# VERTEX_MODEL_NAME=gemini-1.5-pro

# Gemini 2.5 Pro for orchestrator agent (supports tool calling)
# Used by grounding service to coordinate MedGemma + UMLS tools
# No endpoint needed - accessed directly via model name
GEMINI_MODEL_NAME=gemini-2.5-pro

# GCS Bucket for training data and model artifacts
GCS_BUCKET=gs://${bucket_name}

# Optional: Training backend selection ("local" or "vertex")
# TRAINING_BACKEND=vertex

# Optional: Vertex E2E test configuration (for integration tests)
# VERTEX_E2E=1
# VERTEX_E2E_MAX_TOKENS=32
# VERTEX_E2E_PROMPT="Reply with 'ok' only."
EOF
      else
        # Update existing .env file
        update_env_var "${env_path}" "MODEL_BACKEND" "vertex"
        update_env_var "${env_path}" "GCP_PROJECT_ID" "${GCP_PROJECT_ID}"
        update_env_var "${env_path}" "GCP_REGION" "${region}"
        update_env_var "${env_path}" "VERTEX_ENDPOINT_ID" "${endpoint_id}"
        update_env_var "${env_path}" "GEMINI_MODEL_NAME" "gemini-2.5-pro"
        update_env_var "${env_path}" "GCS_BUCKET" "gs://${bucket_name}"
      fi
      echo "✅ Updated .env with Vertex settings"
      echo "  ⚠️  SECURITY: .env contains infrastructure identifiers and is gitignored."
      echo "     Do not commit this file or share it publicly."
    fi
  fi

  echo
  echo "✅ GCP setup complete!"
  if [[ "${WRITE_ENV_TEMPLATE}" == "true" ]]; then
    echo
    echo "To use Vertex AI backend, source the environment file:"
    echo "  source .env"
    echo
    echo "Or export variables manually:"
    echo "  export \$(grep -v '^#' .env | xargs)"
    echo
    echo "Then run your services - they will automatically use Vertex AI."
  fi
}

main "$@"

