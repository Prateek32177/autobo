#!/usr/bin/env bash
# Create a virtual serial pair for Virtual ESP32 ↔ SerialHardwareAdapter.
# Prefers socat; falls back to the Python linked-PTY bridge.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib.sh"

HOST_LINK="${VIRTUAL_ESP32_HOST_PORT:-$RUN_DIR/ttyVESP32-host}"
DEVICE_LINK="${VIRTUAL_ESP32_DEVICE_PORT:-$RUN_DIR/ttyVESP32-device}"
PID_FILE="$RUN_DIR/virtual_esp32_pty.pid"

mkdir -p "$RUN_DIR" "$LOG_DIR"
rm -f "$HOST_LINK" "$DEVICE_LINK"

if [[ -f "$PID_FILE" ]] && kill -0 "$(tr -d '[:space:]' <"$PID_FILE")" 2>/dev/null; then
  echo "PTY bridge already running (pid $(tr -d '[:space:]' <"$PID_FILE"))"
  echo "  host:   $HOST_LINK"
  echo "  device: $DEVICE_LINK"
  exit 0
fi
rm -f "$PID_FILE"

PYTHON="$ROOT/runtime/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

if command -v socat >/dev/null 2>&1; then
  echo "==> Using socat PTY pair"
  # Double-fork via Python so the bridge survives the launching shell (agent/CI).
  "$PYTHON" - "$HOST_LINK" "$DEVICE_LINK" "$PID_FILE" "$LOG_DIR/virtual_esp32_pty.log" <<'PY'
import os, sys, time
from pathlib import Path
host, device, pid_file, log_file = sys.argv[1:5]
Path(pid_file).parent.mkdir(parents=True, exist_ok=True)
if os.fork() > 0:
    # parent waits briefly for grandchild pid file
    for _ in range(50):
        if Path(pid_file).exists():
            break
        time.sleep(0.05)
    raise SystemExit(0)
os.setsid()
if os.fork() > 0:
    os._exit(0)
Path(pid_file).write_text(f"{os.getpid()}\n")
log = open(log_file, "ab", buffering=0)
os.dup2(log.fileno(), 1)
os.dup2(log.fileno(), 2)
os.execvp("socat", [
    "socat", "-d", "-d",
    f"pty,raw,echo=0,link={host},perm=606",
    f"pty,raw,echo=0,link={device},perm=606",
])
PY
else
  echo "==> socat not found — using Python linked PTY bridge"
  "$PYTHON" "$ROOT/firmware/virtual_esp32/run_pty_bridge.py" \
    --host-link "$HOST_LINK" \
    --device-link "$DEVICE_LINK" \
    --daemon \
    --pid-file "$PID_FILE" \
    --log-file "$LOG_DIR/virtual_esp32_pty.log"
fi

for _ in $(seq 1 80); do
  if [[ -e "$HOST_LINK" && -e "$DEVICE_LINK" && -f "$PID_FILE" ]]; then
    if kill -0 "$(tr -d '[:space:]' <"$PID_FILE")" 2>/dev/null; then
      break
    fi
  fi
  sleep 0.05
done

if [[ ! -e "$HOST_LINK" || ! -e "$DEVICE_LINK" ]]; then
  echo "ERROR: failed to create PTY links. See $LOG_DIR/virtual_esp32_pty.log" >&2
  exit 1
fi
if [[ ! -f "$PID_FILE" ]] || ! kill -0 "$(tr -d '[:space:]' <"$PID_FILE")" 2>/dev/null; then
  echo "ERROR: PTY bridge did not stay running. See $LOG_DIR/virtual_esp32_pty.log" >&2
  exit 1
fi

echo "Virtual serial pair ready"
echo "  host (SerialHardwareAdapter): $HOST_LINK"
echo "  device (Virtual ESP32):       $DEVICE_LINK"
echo "  pid: $(tr -d '[:space:]' <"$PID_FILE")"
