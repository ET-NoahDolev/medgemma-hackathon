#!/usr/bin/env bash
# Start both the API server and the HITL UI dev server

set -euo pipefail

# Get the repo root directory (parent of scripts/)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_ROOT"

# Defaults (override via env)
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-3000}"
BASE_PATH="${BASE_PATH:-/demo-app/}"
VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://localhost:${API_PORT}}"

# PIDs for cleanup
BACKEND_PID=""
FRONTEND_PID=""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found in repo root"
    echo "   Create .env with: UMLS_API_KEY=your_key_here"
    echo ""
    echo "   Continuing anyway (will fail if UMLS_API_KEY not set)..."
    echo ""
fi

# Load repo-root .env (if present) for local development.
# This is intentionally simple and supports quoted values/spaces.
if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$REPO_ROOT/.env"
    set +a
fi

# Verify UMLS key is set (either in .env or environment).
if [ -z "${UMLS_API_KEY:-}" ] && [ -z "${GROUNDING_SERVICE_UMLS_API_KEY:-}" ]; then
    echo "❌ Error: UMLS_API_KEY or GROUNDING_SERVICE_UMLS_API_KEY must be set"
    echo ""
    echo "   Option 1: Set in .env file:"
    echo "     echo 'UMLS_API_KEY=your_key' >> .env"
    echo ""
    echo "   Option 2: Set as environment variable:"
    echo "     export UMLS_API_KEY=your_key"
    echo ""
    exit 1
fi

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    if [ -n "${BACKEND_PID}" ]; then
        kill "${BACKEND_PID}" 2>/dev/null || true
    fi
    if [ -n "${FRONTEND_PID}" ]; then
        kill "${FRONTEND_PID}" 2>/dev/null || true
    fi
    exit 0
}

# Trap Ctrl+C and cleanup
trap cleanup SIGINT SIGTERM

echo "🚀 Starting backend and frontend servers..."
echo "   Repo root: $REPO_ROOT"
echo ""

# Start backend API server in background
echo "📡 Starting API server on port ${API_PORT}..."
echo "   API docs: http://localhost:${API_PORT}/docs"
(
    cd "$REPO_ROOT/components/api-service"
    uv run uvicorn api_service.main:app --reload --host "${API_HOST}" --port "${API_PORT}"
) &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Check if backend started successfully
if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
    echo "❌ Backend failed to start"
    exit 1
fi

# Start frontend dev server in background
echo "🎨 Starting frontend dev server..."
echo "   Frontend: http://localhost:${UI_PORT}${BASE_PATH}"
(
    cd "$REPO_ROOT/components/hitl-ui"
    export BASE_PATH
    export VITE_API_BASE_URL
    npm run dev -- --port "${UI_PORT}"
) &
FRONTEND_PID=$!

# Wait a moment for frontend to start
sleep 2

# Check if frontend started successfully
if ! kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    echo "❌ Frontend failed to start"
    kill "${BACKEND_PID}" 2>/dev/null || true
    exit 1
fi

echo ""
echo "✅ Both servers are running!"
echo ""
echo "   Backend API:  http://localhost:${API_PORT}/docs"
echo "   Frontend UI:  http://localhost:${UI_PORT}${BASE_PATH}"
echo ""
echo "   Press Ctrl+C to stop both servers"
echo ""

# Wait for both processes
wait "${BACKEND_PID}" "${FRONTEND_PID}"
