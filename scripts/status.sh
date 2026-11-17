#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"

print_proc() {
  local name="$1"
  local file="$2"
  local url="$3"
  local port="$4"
  local pid
  pid="$(read_pid "$file")"
  if pid_alive "$pid"; then
    if curl -sf "$url" >/dev/null 2>&1; then
      echo "$name: running (pid $pid) — $url OK"
    else
      echo "$name: process alive (pid $pid) but $url not responding"
    fi
    return 0
  fi

  if port_in_use "$port" && curl -sf "$url" >/dev/null 2>&1; then
    local listener=""
    if command -v lsof >/dev/null 2>&1; then
      listener="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -n1 || true)"
    fi
    echo "$name: reachable at $url but PID file stale${listener:+ (listener pid $listener)}"
    if [[ -n "$listener" ]]; then
      write_pid "$file" "$listener"
      echo "         updated $file -> $listener"
    fi
    return 0
  fi

  if [[ -n "$pid" ]]; then
    echo "$name: not running (stale pid $pid)"
    clear_pid "$file"
  else
    echo "$name: not running"
  fi
}

print_proc "runtime  " "$RUNTIME_PID_FILE" "$RUNTIME_URL/ready" "$RUNTIME_PORT"
print_proc "dashboard" "$DASHBOARD_PID_FILE" "$DASHBOARD_URL" "$DASHBOARD_PORT"

if curl -sf "$RUNTIME_URL/ready" >/dev/null 2>&1; then
  curl -s "$RUNTIME_URL/ready" | python3 -m json.tool 2>/dev/null || curl -s "$RUNTIME_URL/ready"
fi
