#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cleanup() {
  if [[ -n "${RUNTIME_PID:-}" ]]; then
    kill "$RUNTIME_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "==> Starting Physical AI runtime on http://127.0.0.1:8000"
cd "$ROOT/runtime"
# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
python -m physical_ai &
RUNTIME_PID=$!

# Wait for health
for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
    break
  fi
  sleep 0.2
done

echo "==> Starting dashboard on http://127.0.0.1:3000"
cd "$ROOT/apps/dashboard"
npm run dev -- --port 3000
