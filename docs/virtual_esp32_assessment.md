# Virtual ESP32 — inspection notes

## Reuse

- Protocol contracts: `contracts/protocol/messages.py`
- Host path: `SerialTransport` → `ProtocolSession` → `Esp32HardwareAdapter` (`SerialHardwareAdapter` alias)
- DeviceRegistry serial branch already uses that adapter (no mock shortcut)

## Firmware ↔ contract mismatches (to fix)

| Issue | Firmware today | Target |
|---|---|---|
| Action validation | ACK accepted before action check | Reject unknown actions |
| `read_encoders` | Missing | Return encoder deltas (0 if idle) |
| Motor direction | Always `forward` when active | Report actual left/right directions |
| Turns | Same delta both encoders | Opposite deltas for turn_left/right |
| Malformed JSON | Updates `last_host_ms` | Must **not** feed watchdog |
| Emergency stop message | Stops motors, no ACK/result | ACK+result when `command_id` present; always stop |
| Telemetry | No `emergency_stopped` | Include latch flag |

## Virtual ESP32 approach

- Independent process in `firmware/virtual_esp32/`
- Speaks JSON Lines over a real PTY (`socat` or `pty`)
- Host uses unchanged `SerialHardwareAdapter` / `SerialTransport`
- `MockHardwareAdapter` untouched
