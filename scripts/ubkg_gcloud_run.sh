#!/usr/bin/env bash
set -euo pipefail

# ---------- logging ----------
LOG_DIR="${LOG_DIR:-./gcp-deploy-logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/deploy_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

log() { printf "[%s] %s\n" "$(date -Iseconds)" "$*"; }
die() { log "ERROR: $*"; exit 1; }

on_err() {
  local exit_code=$?
  log "FAILED (exit=$exit_code) at line ${BASH_LINENO[0]}: ${BASH_COMMAND}"
  log "Log file: $LOG_FILE"
  exit "$exit_code"
}
trap on_err ERR

# ---------- user config (edit these) ----------
PROJECT_ID="${PROJECT_ID:-YOUR_PROJECT_ID}"
REGION="${REGION:-europe-west1}"
SERVICE_NAME="${SERVICE_NAME:-my-service}"
REPO_NAME="${REPO_NAME:-containers}"
IMAGE_NAME="${IMAGE_NAME:-app}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"

# If true -> public HTTPS endpoint; if false -> requires IAM auth
PUBLIC="${PUBLIC:-true}"

# ---------- prereqs ----------
command -v bash >/dev/null 2>&1 || die "bash not found (unexpected on macOS)."

if ! command -v brew >/dev/null 2>&1; then
  die "Homebrew is required. Install it from https://brew.sh/ and re-run."
fi

if ! command -v gcloud >/dev/null 2>&1; then
  log "Installing Google Cloud CLI (google-cloud-sdk) via Homebrew..."
  brew install --cask google-cloud-sdk
fi

# Optional but helps avoid interactive prompts in CI-ish runs
GCLOUD_QUIET_FLAG="--quiet"

# ---------- validate project ----------
if [[ "$PROJECT_ID" == "YOUR_PROJECT_ID" ]]; then
  die "Set PROJECT_ID (env var or edit script)."
fi

log "Setting active project to: $PROJECT_ID"
gcloud config set project "$PROJECT_ID" $GCLOUD_QUIET_FLAG

# Confirm user is authenticated (interactive login is not automated here)
ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n 1 || true)"
if [[ -z "${ACTIVE_ACCOUNT:-}" ]]; then
  die "No active gcloud account. Run: gcloud auth login"
fi
log "Active gcloud account: $ACTIVE_ACCOUNT"

# ---------- enable APIs ----------
log "Enabling required APIs..."
gcloud services enable \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  $GCLOUD_QUIET_FLAG

# ---------- artifact registry repo ----------
log "Ensuring Artifact Registry repo exists: $REPO_NAME ($REGION)"
if ! gcloud artifacts repositories describe "$REPO_NAME" --location "$REGION" $GCLOUD_QUIET_FLAG >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Docker images for $SERVICE_NAME" \
    $GCLOUD_QUIET_FLAG
  log "Created repo: $REPO_NAME"
else
  log "Repo already exists: $REPO_NAME"
fi

# ---------- build + push (Cloud Build) ----------
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${TAG}"
log "Building & pushing image with Cloud Build: $IMAGE_URI"
gcloud builds submit --tag "$IMAGE_URI" $GCLOUD_QUIET_FLAG .

# ---------- deploy to Cloud Run ----------
log "Deploying to Cloud Run service: $SERVICE_NAME (region: $REGION)"
AUTH_FLAG="--no-allow-unauthenticated"
if [[ "$PUBLIC" == "true" ]]; then AUTH_FLAG="--allow-unauthenticated"; fi

gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE_URI" \
  --region "$REGION" \
  "$AUTH_FLAG" \
  $GCLOUD_QUIET_FLAG

SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format='value(status.url)' 2>/dev/null || true)"
log "Deployment complete."
log "Service URL: ${SERVICE_URL:-<unknown>}"
log "Logs: $LOG_FILE"
