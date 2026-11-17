#!/usr/bin/env bash
# Shared helpers for Physical AI local deployment scripts.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/.run"
LOG_DIR="$ROOT/logs"
RUNTIME_PID_FILE="$RUN_DIR/runtime.pid"
DASHBOARD_PID_FILE="$RUN_DIR/dashboard.pid"
RUNTIME_LOG="$LOG_DIR/runtime.log"
DASHBOARD_LOG="$LOG_DIR/dashboard.log"
RUNTIME_HOST="${PHYSICAL_AI_HOST:-127.0.0.1}"
RUNTIME_PORT="${PHYSICAL_AI_PORT:-8000}"
DASHBOARD_PORT="${PHYSICAL_AI_DASHBOARD_PORT:-3000}"
RUNTIME_URL="http://${RUNTIME_HOST}:${RUNTIME_PORT}"
DASHBOARD_URL="http://127.0.0.1:${DASHBOARD_PORT}"

mkdir -p "$RUN_DIR" "$LOG_DIR"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $1" >&2
    return 1
  fi
}

version_ge() {
  # usage: version_ge "$actual" "$required"
  printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1 | grep -qx "$2"
}

python_bin() {
  if [[ -x "$ROOT/runtime/.venv/bin/python" ]]; then
    echo "$ROOT/runtime/.venv/bin/python"
  else
    command -v python3
  fi
}

activate_runtime_venv() {
  # shellcheck disable=SC1091
  source "$ROOT/runtime/.venv/bin/activate"
}

pid_alive() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

read_pid() {
  local file="$1"
  if [[ -f "$file" ]]; then
    tr -d '[:space:]' <"$file"
  fi
}

write_pid() {
  local file="$1"
  local pid="$2"
  echo "$pid" >"$file"
}

clear_pid() {
  local file="$1"
  rm -f "$file"
}

port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  else
    return 1
  fi
}

wait_http() {
  local url="$1"
  local attempts="${2:-40}"
  local delay="${3:-0.25}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

our_runtime_running() {
  local pid
  pid="$(read_pid "$RUNTIME_PID_FILE")"
  pid_alive "$pid"
}

our_dashboard_running() {
  local pid
  pid="$(read_pid "$DASHBOARD_PID_FILE")"
  pid_alive "$pid"
}
