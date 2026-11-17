# M2 — Hardware Architecture Refactoring Plan

## M1 map (reuse)

| Area | Keep / extend |
|---|---|
| `HardwareAdapter` ABC | Keep as **facade**; stop treating it as transport |
| `MockHardwareAdapter` | Preserve simulation behaviour; rewire internals |
| `SerialHardwareAdapter` stub | Replace with `Esp32HardwareAdapter` + `SerialTransport` |
| `contracts/protocol/messages.py` | Extend (handshake, version, errors) |
| `DeviceRegistry` | Keep identity/lifecycle; remove metric hardcoding |
| DB component rows | Keep as persistence; operational adapters live in ComponentRegistry |
| Dashboard / FastAPI | Preserve M1 APIs; enrich meta |

## Missing interfaces

1. `TransportAdapter` — connect/read/write/state/errors  
2. `ProtocolSession` — framing, handshake, correlation, dispatch  
3. `ComponentAdapter` — health/metrics/diagnostics/capabilities/execute  
4. `ComponentRegistry` — live adapters per device  
5. `CapabilityRegistry` — capability definitions + dynamic AI tools  
6. Safety validator + action executor pipeline (thin M2 stubs)  
7. ESP32 firmware peer  

## Implementation order

1. Protocol handshake + shared health models  
2. Transport + ProtocolSession (+ memory transport for tests)  
3. Component adapters + registries  
4. HardwareAdapter facades (Mock, ESP32)  
5. Thin DeviceRegistry + telemetry dispatch  
6. Execution/AI tool generation stubs  
7. Firmware peer  
8. Tests (M1 green + M2 acceptance)

## Non-goals

Arduino/RPi/STM32 implementations, MQTT, ROS, cloud, full LLM planning.
