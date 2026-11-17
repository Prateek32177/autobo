#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib.sh"

stop_file() {
  local name="$1"
  local file="$2"
  local pid
  pid="$(read_pid "$file")"
  if [[ -z "$pid" ]]; then
    echo "$name: not tracked"
    return 0
  fi
  if pid_alive "$pid"; then
    echo "$name: stopping pid $pid"
    kill "$pid" 2>/dev/null || true
    sleep 0.2
    kill -9 "$pid" 2>/dev/null || true
  else
    echo "$name: stale pid $pid"
  fi
  clear_pid "$file"
}

stop_file "virtual_esp32" "$RUN_DIR/virtual_esp32.pid"
stop_file "virtual_esp32_pty" "$RUN_DIR/virtual_esp32_pty.pid"
rm -f "$RUN_DIR/ttyVESP32-host" "$RUN_DIR/ttyVESP32-device"
echo "Virtual ESP32 stopped"
