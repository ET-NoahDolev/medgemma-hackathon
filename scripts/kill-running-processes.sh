#!/usr/bin/env bash
# Kill API and frontend UI processes (including uvicorn reload/workers and Vite dev server trees).

set -euo pipefail

# Default ports (can be overridden via env)
API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-3000}"

echo "🔍 Searching for API and frontend UI processes (API port ${API_PORT}, UI port ${UI_PORT})..."

# Output PIDs for the given port via lsof; no extra echo of PIDs (caller parses lines).
pids_on_port() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -ti ":$port" 2>/dev/null || true
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tuln 2>/dev/null | grep ":$port " | awk '{print $NF}' | cut -d'/' -f1 | sort -u || true
    else
        true
    fi
}

# Recursively collect descendant PIDs (children, grandchildren, ...).
descendants_of() {
    local pid=$1
    local kids
    kids=$(pgrep -P "$pid" 2>/dev/null || true)
    for k in $kids; do
        echo "$k"
        descendants_of "$k"
    done
}

# Collect PIDs for API and frontend UI: port listeners and known process patterns.
# Includes all descendants so we kill reload watchers, async workers, and Vite parent/child trees.
collect_pids_to_kill() {
    local roots=""

    # API: processes on API port
    local p
    for p in $(pids_on_port "$API_PORT"); do
        [ -z "$p" ] && continue
        roots="$roots $p"
    done
    # API: uvicorn api_service.main (parent and/or worker)
    for p in $(pgrep -f "uvicorn.*api_service\.main" 2>/dev/null || true); do
        [ -z "$p" ] && continue
        roots="$roots $p"
    done

    # Frontend: processes on UI port
    for p in $(pids_on_port "$UI_PORT"); do
        [ -z "$p" ] && continue
        roots="$roots $p"
    done
    # Frontend: Vite dev server (e.g. npm run dev -- --port N)
    for p in $(pgrep -f "vite.*--port" 2>/dev/null || true); do
        [ -z "$p" ] && continue
        roots="$roots $p"
    done

    roots=$(echo "$roots" | tr ' ' '\n' | sort -u | grep -v '^$' | tr '\n' ' ')
    local out="$roots"
    for r in $roots; do
        out="$out $(descendants_of "$r")"
    done
    echo "$out" | tr ' ' '\n' | sort -u | grep -v '^$' | tr '\n' ' '
}

PIDS_TO_KILL=$(collect_pids_to_kill)

# Remove duplicates and empty values
PIDS_TO_KILL=$(echo "$PIDS_TO_KILL" | tr ' ' '\n' | sort -u | grep -v '^$' | tr '\n' ' ')

if [ -z "$PIDS_TO_KILL" ]; then
    echo ""
    echo "✅ No API or frontend UI processes found to kill"
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
