#!/bin/bash
# Start both the API server and frontend dev server

set -e

# Get the repo root directory (parent of scripts/)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_ROOT"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found in repo root"
    echo "   Create .env with: UMLS_API_KEY=your_key_here"
    echo ""
    echo "   Continuing anyway (will fail if UMLS_API_KEY not set)..."
    echo ""
fi

# Verify UMLS_API_KEY is set (either in .env or environment)
if [ -z "${UMLS_API_KEY}" ] && [ -z "${GROUNDING_SERVICE_UMLS_API_KEY}" ]; then
    if [ -f ".env" ]; then
        # Try to load from .env
        export $(grep -v '^#' .env | xargs)
    fi
    
    if [ -z "${UMLS_API_KEY}" ] && [ -z "${GROUNDING_SERVICE_UMLS_API_KEY}" ]; then
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
fi

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    exit 0
}

# Trap Ctrl+C and cleanup
trap cleanup SIGINT SIGTERM

echo "🚀 Starting backend and frontend servers..."
echo "   Repo root: $REPO_ROOT"
echo ""

# Set PYTHONPATH for monorepo structure
export PYTHONPATH="components/api-service/src:components/data-pipeline/src:components/extraction-service/src:components/grounding-service/src:components/shared/src"

# Start backend API server in background
echo "📡 Starting API server on port 8000..."
echo "   API docs: http://localhost:8000/docs"
uv run uvicorn api_service.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Check if backend started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ Backend failed to start"
    exit 1
fi

# Start frontend dev server in background
echo "🎨 Starting frontend dev server..."
echo "   Frontend: http://localhost:3000/demo-app/"
cd "$REPO_ROOT/components/hitl-ui"
npm run dev &
FRONTEND_PID=$!

# Wait a moment for frontend to start
sleep 2

# Check if frontend started successfully
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "❌ Frontend failed to start"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo "✅ Both servers are running!"
echo ""
echo "   Backend API:  http://localhost:8000/docs"
echo "   Frontend UI:  http://localhost:3000/demo-app/"
echo ""
echo "   Press Ctrl+C to stop both servers"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
