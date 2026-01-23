#!/usr/bin/env bash
# Kill any running processes from previous sessions (API server, UI, MLflow, etc.)

set -euo pipefail

# Get the repo root directory
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Default ports (can be overridden via env)
API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-3000}"
MLFLOW_PORT="${MLFLOW_PORT:-5000}"

echo "🔍 Searching for running processes..."

# Find processes by port
find_processes_by_port() {
    local port=$1
    local name=$2
    echo ""
    echo "Checking port ${port} (${name})..."
    
    if command -v lsof >/dev/null 2>&1; then
        # macOS/Linux with lsof
        local pids=$(lsof -ti ":$port" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "  Found processes on port ${port}:"
            for pid in $pids; do
                ps -p "$pid" -o pid=,command= 2>/dev/null || true
            done
            echo "$pids"
        else
            echo "  No processes found on port ${port}"
            echo ""
        fi
    elif command -v netstat >/dev/null 2>&1; then
        # Alternative: netstat (less reliable)
        local pids=$(netstat -tuln 2>/dev/null | grep ":$port " | awk '{print $NF}' | cut -d'/' -f1 | sort -u || true)
        if [ -n "$pids" ]; then
            echo "  Found processes on port ${port}:"
            for pid in $pids; do
                ps -p "$pid" -o pid=,command= 2>/dev/null || true
            done
            echo "$pids"
        else
            echo "  No processes found on port ${port}"
            echo ""
        fi
    else
        echo "  ⚠️  Cannot check port ${port}: lsof or netstat not available"
        echo ""
    fi
}

# Find processes by command pattern
find_processes_by_pattern() {
    local pattern=$1
    local name=$2
    echo ""
    echo "Checking for ${name} processes..."
    
    # Find processes matching the pattern
    local pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "  Found ${name} processes:"
        for pid in $pids; do
            ps -p "$pid" -o pid=,command= 2>/dev/null || true
        done
        echo "$pids"
    else
        echo "  No ${name} processes found"
        echo ""
    fi
}

# Collect all PIDs to kill
PIDS_TO_KILL=""

# Check ports
API_PIDS=$(find_processes_by_port "$API_PORT" "API server")
if [ -n "$API_PIDS" ]; then
    PIDS_TO_KILL="$PIDS_TO_KILL $API_PIDS"
fi

UI_PIDS=$(find_processes_by_port "$UI_PORT" "Frontend UI")
if [ -n "$UI_PIDS" ]; then
    PIDS_TO_KILL="$PIDS_TO_KILL $UI_PIDS"
fi

MLFLOW_PIDS=$(find_processes_by_port "$MLFLOW_PORT" "MLflow UI")
if [ -n "$MLFLOW_PIDS" ]; then
    PIDS_TO_KILL="$PIDS_TO_KILL $MLFLOW_PIDS"
fi

# Check for uvicorn processes
UVICORN_PIDS=$(find_processes_by_pattern "uvicorn.*api_service.main" "uvicorn API")
if [ -n "$UVICORN_PIDS" ]; then
    PIDS_TO_KILL="$PIDS_TO_KILL $UVICORN_PIDS"
fi

# Check for npm/vite processes
VITE_PIDS=$(find_processes_by_pattern "vite.*--port.*${UI_PORT}" "Vite dev server")
if [ -n "$VITE_PIDS" ]; then
    PIDS_TO_KILL="$PIDS_TO_KILL $VITE_PIDS"
fi

# Check for mlflow ui processes
MLFLOW_UI_PIDS=$(find_processes_by_pattern "mlflow.*ui" "MLflow UI")
if [ -n "$MLFLOW_UI_PIDS" ]; then
    PIDS_TO_KILL="$PIDS_TO_KILL $MLFLOW_UI_PIDS"
fi

# Remove duplicates and empty values
PIDS_TO_KILL=$(echo "$PIDS_TO_KILL" | tr ' ' '\n' | sort -u | grep -v '^$' | tr '\n' ' ')

if [ -z "$PIDS_TO_KILL" ]; then
    echo ""
    echo "✅ No running processes found to kill"
    exit 0
fi

echo ""
echo "📋 Processes to kill:"
for pid in $PIDS_TO_KILL; do
    ps -p "$pid" -o pid=,command= 2>/dev/null || echo "  PID $pid (process may have already terminated)"
done

echo ""
read -p "Kill these processes? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 0
fi

# Kill processes
KILLED=0
FAILED=0

for pid in $PIDS_TO_KILL; do
    if kill -0 "$pid" 2>/dev/null; then
        echo "  Killing PID $pid..."
        if kill "$pid" 2>/dev/null; then
            KILLED=$((KILLED + 1))
            # Wait a bit, then force kill if still running
            sleep 1
            if kill -0 "$pid" 2>/dev/null; then
                echo "    Force killing PID $pid..."
                kill -9 "$pid" 2>/dev/null || true
            fi
        else
            echo "    ⚠️  Failed to kill PID $pid"
            FAILED=$((FAILED + 1))
        fi
    else
        echo "  PID $pid already terminated"
    fi
done

echo ""
if [ $FAILED -eq 0 ]; then
    echo "✅ Successfully killed $KILLED process(es)"
else
    echo "⚠️  Killed $KILLED process(es), $FAILED failed"
fi
