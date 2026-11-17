# Firmware Serial Protocol

USB serial, **115200** baud, **JSON Lines** (one JSON object per line).

## Protocol version

Current version: **1.0** (`PROTOCOL_VERSION` in `contracts/protocol/messages.py`).

## Message types

| Type | Direction | Purpose |
|---|---|---|
| `handshake` | Device → Host | Identity, protocol version, components/capabilities |
| `handshake_ack` | Host → Device | Accept / reject protocol version |
| `heartbeat` | Device → Host | Connectivity / uptime |
| `telemetry` | Device → Host | Sensors, encoders, battery, motors |
| `command` | Host → Device | Bounded action request |
| `command_ack` | Device → Host | Accept / reject |
| `command_result` | Device → Host | Completion with observed deltas |
| `emergency_stop` | Host ↔ Device | Immediate motor stop |
| `error` | Device → Host | Malformed input / protocol errors |

See `contracts/protocol/messages.py` for the authoritative Pydantic models.

## Safety

- Every command has a `command_id`.
- Firmware validates actions and parameters.
- Motor commands have a timeout; watchdog stops motors on host disconnect.
- Malformed lines are ignored or answered with a rejected ack — never treated as GPIO ops.
