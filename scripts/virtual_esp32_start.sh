#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib.sh"

DEVICE_LINK="${VIRTUAL_ESP32_DEVICE_PORT:-$RUN_DIR/ttyVESP32-device}"
PID_FILE="$RUN_DIR/virtual_esp32.pid"
SCENARIO="${VIRTUAL_ESP32_SCENARIO:-normal}"

if [[ ! -e "$DEVICE_LINK" ]]; then
  echo "==> Creating virtual serial pair"
  "$ROOT/scripts/virtual_esp32_pty.sh"
fi

if [[ -f "$PID_FILE" ]] && kill -0 "$(tr -d '[:space:]' <"$PID_FILE")" 2>/dev/null; then
  echo "Virtual ESP32 already running (pid $(tr -d '[:space:]' <"$PID_FILE"))"
  exit 0
fi
rm -f "$PID_FILE"

require_cmd python3
PYTHON="$ROOT/runtime/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

echo "==> Starting Virtual ESP32 on $DEVICE_LINK (scenario=$SCENARIO)"
"$PYTHON" "$ROOT/firmware/virtual_esp32/simulator.py" \
  --port "$DEVICE_LINK" \
  --scenario "$SCENARIO" \
  -v \
  --daemon \
  --pid-file "$PID_FILE" \
  --log-file "$LOG_DIR/virtual_esp32.log"

for _ in $(seq 1 40); do
  if [[ -f "$PID_FILE" ]] && kill -0 "$(tr -d '[:space:]' <"$PID_FILE")" 2>/dev/null; then
    break
  fi
  sleep 0.05
done

if [[ ! -f "$PID_FILE" ]] || ! kill -0 "$(tr -d '[:space:]' <"$PID_FILE")" 2>/dev/null; then
  echo "ERROR: Virtual ESP32 failed to start. See $LOG_DIR/virtual_esp32.log" >&2
  exit 1
fi

HOST_LINK="${VIRTUAL_ESP32_HOST_PORT:-$RUN_DIR/ttyVESP32-host}"
echo "Virtual ESP32 running (pid $(tr -d '[:space:]' <"$PID_FILE"))"
echo "Register a serial device with port: $HOST_LINK"
echo "Example:"
echo "  curl -s -X POST http://127.0.0.1:8000/api/devices -H 'Content-Type: application/json' -d '{"
echo "    \"name\": \"Virtual Rover\","
echo "    \"connection\": {\"type\": \"serial\", \"port\": \"$HOST_LINK\", \"baud_rate\": 115200},"
echo "    \"firmware_version\": \"0.2.0\""
echo "  }'"
