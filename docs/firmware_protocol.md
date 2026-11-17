# Firmware Serial Protocol

USB serial, **115200** baud, **JSON Lines** (one JSON object per line).

## Message types

| Type | Direction | Purpose |
|---|---|---|
| `heartbeat` | Device → Host | Connectivity / uptime |
| `telemetry` | Device → Host | Sensors, encoders, battery, motors |
| `command` | Host → Device | Bounded action request |
| `command_ack` | Device → Host | Accept / reject |
| `command_result` | Device → Host | Completion with observed deltas |
| `emergency_stop` | Host ↔ Device | Immediate motor stop |

See `contracts/protocol/messages.py` for the authoritative Pydantic models.

## Safety

- Every command has a `command_id`.
- Firmware validates actions and parameters.
- Motor commands have a timeout; watchdog stops motors on host disconnect.
- Malformed lines are ignored or answered with a rejected ack — never treated as GPIO ops.
