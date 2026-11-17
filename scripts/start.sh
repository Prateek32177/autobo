#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"

require_cmd curl

if [[ ! -x "$ROOT/runtime/.venv/bin/python" ]]; then
  echo "ERROR: runtime venv missing. Run ./scripts/setup.sh first." >&2
  exit 1
fi

start_runtime() {
  if our_runtime_running; then
    echo "Runtime already running (pid $(read_pid "$RUNTIME_PID_FILE"))"
    return 0
  fi
  clear_pid "$RUNTIME_PID_FILE"
  if port_in_use "$RUNTIME_PORT"; then
    echo "ERROR: port $RUNTIME_PORT is in use by another process." >&2
    echo "Stop that process or set PHYSICAL_AI_PORT, then retry." >&2
    exit 1
  fi
  echo "==> Starting runtime on $RUNTIME_URL"
  cd "$ROOT/runtime"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
  if [[ -f "$ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$ROOT/.env"
    set +a
  fi
  # nohup + disown keeps the process after this script exits (macOS/Linux).
  nohup python -m physical_ai >>"$RUNTIME_LOG" 2>&1 </dev/null &
  write_pid "$RUNTIME_PID_FILE" $!
  disown $! 2>/dev/null || true
  if ! wait_http "$RUNTIME_URL/ready" 60 0.25; then
    echo "ERROR: runtime failed to become ready. See $RUNTIME_LOG" >&2
    clear_pid "$RUNTIME_PID_FILE"
    exit 1
  fi
  echo "Runtime ready (pid $(read_pid "$RUNTIME_PID_FILE"))"
}

start_dashboard() {
  if our_dashboard_running; then
    echo "Dashboard already running (pid $(read_pid "$DASHBOARD_PID_FILE"))"
    return 0
  fi
  clear_pid "$DASHBOARD_PID_FILE"
  if port_in_use "$DASHBOARD_PORT"; then
    echo "ERROR: port $DASHBOARD_PORT is in use by another process." >&2
    echo "Stop that process or set PHYSICAL_AI_DASHBOARD_PORT, then retry." >&2
    exit 1
  fi
  echo "==> Starting dashboard on $DASHBOARD_URL"
  cd "$ROOT/apps/dashboard"
  nohup npm run dev -- --port "$DASHBOARD_PORT" >>"$DASHBOARD_LOG" 2>&1 </dev/null &
  write_pid "$DASHBOARD_PID_FILE" $!
  disown $! 2>/dev/null || true
  if ! wait_http "$DASHBOARD_URL" 80 0.25; then
    echo "ERROR: dashboard failed to start. See $DASHBOARD_LOG" >&2
    exit 1
  fi
  # Prefer the listener PID if npm reaped itself and left Next.js running.
  if command -v lsof >/dev/null 2>&1; then
    listener="$(lsof -nP -iTCP:"$DASHBOARD_PORT" -sTCP:LISTEN -t 2>/dev/null | head -n1 || true)"
    if [[ -n "$listener" ]]; then
      write_pid "$DASHBOARD_PID_FILE" "$listener"
    fi
  fi
  echo "Dashboard ready (pid $(read_pid "$DASHBOARD_PID_FILE"))"
}

start_runtime
start_dashboard

echo ""
echo "Physical AI is running locally"
echo "  Dashboard: $DASHBOARD_URL"
echo "  Runtime:   $RUNTIME_URL"
echo "  Ready:     $RUNTIME_URL/ready"
echo "  Logs:      $LOG_DIR"
echo "Stop with:   ./scripts/stop.sh"
