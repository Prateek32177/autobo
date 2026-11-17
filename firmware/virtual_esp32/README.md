# Virtual ESP32

Protocol-level ESP32 simulator that exercises the **real** serial path:

`Virtual ESP32` → PTY → `SerialTransport` → `ProtocolSession` → `Esp32HardwareAdapter` / `SerialHardwareAdapter`

It does **not** use `MockHardwareAdapter`. The dashboard must show `connection_type: serial`.

Aligned with:

- `firmware/esp32/src/main.cpp`
- `contracts/protocol/messages.py`

## Identity

| Field | Value |
|---|---|
| device_id | `rover-001` |
| board | `esp32` |
| model | `autonomous_rover` |
| firmware_version | `0.2.0` |
| protocol_version | `1.0` |

## Prerequisites

- Python 3.12+ with `pyserial` (runtime venv)
- Optional: `socat` (preferred PTY pair). If missing, scripts fall back to a Python linked-PTY bridge (daemonized).

```bash
# macOS (optional)
brew install socat
```

## Startup

```bash
# 1) Physical AI runtime + dashboard
./scripts/start.sh

# 2) Virtual serial pair + Virtual ESP32 (independent processes)
./scripts/virtual_esp32_start.sh

# 3) Register + connect a SERIAL device using the HOST PTY (absolute path)
HOST_PORT="$PWD/.run/ttyVESP32-host"

curl -s -X POST http://127.0.0.1:8000/api/devices \
  -H 'Content-Type: application/json' \
  -d "{
    \"name\": \"Virtual Rover\",
    \"device_type\": \"autonomous_rover\",
    \"connection\": {
      \"type\": \"serial\",
      \"port\": \"$HOST_PORT\",
      \"baud_rate\": 115200
    },
    \"firmware_version\": \"0.2.0\"
  }"

# Use the returned device id:
curl -s -X POST http://127.0.0.1:8000/api/hardware/connect \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"<device-id>"}'

# Optional: drive + emergency stop through the same serial path
curl -s -X POST http://127.0.0.1:8000/api/hardware/invoke \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"<device-id>","capability":"move_forward","parameters":{"speed":0.25,"duration_ms":120}}'
curl -s -X POST http://127.0.0.1:8000/api/hardware/emergency-stop \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"<device-id>"}'
```

Open the dashboard Devices page — the device must show **serial** (`is_simulation: false`), not MockHardwareAdapter.

PTY bridge and simulator double-fork into the background; PIDs live under `.run/`.

**Important:** one Virtual ESP32 PTY pair supports **one** connected serial device. Registering several “Virtual Rover” rows that all use `.run/ttyVESP32-host` will fail the second connect (port in use) and used to corrupt the first session. For two serial rovers, run two independent PTY/simulator pairs on different ports.

## Shutdown

```bash
./scripts/virtual_esp32_stop.sh
./scripts/stop.sh   # optional: stop runtime/dashboard
```

## Scenarios

```bash
VIRTUAL_ESP32_SCENARIO=low_battery ./scripts/virtual_esp32_start.sh
VIRTUAL_ESP32_SCENARIO=sensor_failure ./scripts/virtual_esp32_start.sh
VIRTUAL_ESP32_SCENARIO=command_timeout ./scripts/virtual_esp32_start.sh
```

| Scenario | Behaviour |
|---|---|
| `normal` | Full protocol |
| `low_battery` | Battery ~6.5 V |
| `sensor_failure` | Distance reads fail / sentinel |
| `heartbeat_timeout` | Stops outbound traffic |
| `stale_telemetry` | Heartbeat only |
| `malformed_json` | Emits a bad line once |
| `command_timeout` | ACK without result |
| `host_disconnect` | Ignores host (watchdog) |
| `device_disconnect` | Closes serial after delay |

## Manual run

```bash
./scripts/virtual_esp32_pty.sh
cd firmware/virtual_esp32
../../runtime/.venv/bin/python simulator.py --port ../../.run/ttyVESP32-device --scenario normal -v
```

## Logs

- `.run/` — PTY symlinks + PIDs  
- `logs/virtual_esp32.log`  
- `logs/virtual_esp32_pty.log`
