#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"

stop_tracked() {
  local name="$1"
  local file="$2"
  local port="$3"
  local pid
  pid="$(read_pid "$file")"

  if [[ -n "$pid" ]] && pid_alive "$pid"; then
    echo "$name: stopping tracked pid $pid"
    # Kill descendants first (npm -> next-server, etc.).
    pkill -P "$pid" 2>/dev/null || true
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 30); do
      if ! pid_alive "$pid"; then
        break
      fi
      sleep 0.1
    done
    if pid_alive "$pid"; then
      echo "$name: forcing kill pid $pid"
      pkill -9 -P "$pid" 2>/dev/null || true
      kill -9 "$pid" 2>/dev/null || true
    fi
    clear_pid "$file"
    echo "$name: stopped"
    return 0
  fi

  # Only reclaim the port if it still serves our expected local URL path and
  # we previously tracked this app (stale pid file or known port ownership).
  if [[ -n "$pid" ]]; then
    echo "$name: clearing stale pid $pid"
    clear_pid "$file"
  else
    echo "$name: not tracked"
  fi

  if port_in_use "$port"; then
    local listener=""
    listener="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -n1 || true)"
    if [[ -n "$listener" ]]; then
      # Safety: only kill listener if command line looks like our app.
      local cmd
      cmd="$(ps -p "$listener" -o args= 2>/dev/null || true)"
      if echo "$cmd" | grep -Eq "physical_ai|next dev|next-server|node.*dashboard"; then
        echo "$name: stopping leftover listener pid $listener"
        kill "$listener" 2>/dev/null || true
        sleep 0.2
        kill -9 "$listener" 2>/dev/null || true
      else
        echo "$name: port $port held by unrelated process (pid $listener) — not killed"
      fi
    fi
  fi
}

stop_tracked "dashboard" "$DASHBOARD_PID_FILE" "$DASHBOARD_PORT"
stop_tracked "runtime" "$RUNTIME_PID_FILE" "$RUNTIME_PORT"

echo "Done. Unrelated processes were not touched."
