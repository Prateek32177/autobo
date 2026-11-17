# Physical AI — Architecture & Implementation Plan

**Product:** Local-first Physical AI Developer Platform  
**Initial application:** Autonomous Rover  
**Scope of this document:** Planning for MVP + Milestone 1 delivery notes

---

## 1. Phased implementation plan

### Milestone 1 — Local runtime foundation *(current)*

| Task | Deliverable |
|---|---|
| Monorepo scaffold | `apps/`, `runtime/`, `sdk/`, `firmware/`, `contracts/`, `docs/`, `scripts/` |
| Shared contracts | Pydantic/JSON schemas for devices, components, telemetry, protocol messages |
| FastAPI runtime | Localhost API + WebSocket |
| SQLite storage | `devices`, `components`, `telemetry`, `diagnostic_events` (+ stubs for later tables) |
| Device registry | Manual register/list/get/delete |
| Hardware abstraction | `HardwareAdapter` protocol + **mock** adapter |
| Dashboard shell | Overview + Devices; shows **explicitly simulated** device |
| Tests + docs | Pytest, README, setup scripts |

**Exit criteria:** App starts locally; dashboard shows a simulated device with component health and sample telemetry.

### Milestone 2 — ESP32 integration

PlatformIO firmware, JSON Lines protocol, heartbeat/telemetry/commands, real serial adapter, live ESP32 telemetry on dashboard.

### Milestone 3 — Observability and diagnostics

Component health model, deterministic diagnostic rules, event history, failure demos (sensor disconnect).

### Milestone 4 — LLM integration

LiteLLM provider abstraction, OS keyring credentials, structured task planning, AI diagnostics, no-LLM mode.

### Milestone 5 — Safe execution

Action registry, capability + safety validation, executor, cancellation, outcome verification.

### Milestone 6 — Rover reference application

Motors, encoders, distance, battery, camera, bounded autonomous demos.

---

## 2. Shared data models & serial protocol (define first)

These contracts are the integration spine between firmware, runtime, SDK and dashboard.

### Device & component models

- `Device` — id, name, type, connection, firmware, status, components, capabilities
- `Component` — id, device_id, name, type, adapter_type, health, last metrics
- `ConnectionConfig` — `simulation` | `serial` (+ port/baud)
- `HealthStatus` — `healthy` | `degraded` | `unhealthy` | `unknown` | `disconnected`
- `Capability` — named action with parameter schema metadata

### Telemetry & events

- `TelemetrySample` — device/component, metric name/value, timestamp
- `DiagnosticEvent` — code, severity, evidence, expected/observed
- `ExecutionEvent` — task-scoped action lifecycle (Milestone 5+)
- `Heartbeat` — device_id, firmware_version, uptime_ms

### Serial protocol (JSON Lines, 115200 baud)

Message `type` values: `heartbeat`, `telemetry`, `command`, `command_ack`, `command_result`, `emergency_stop`

Every command carries `command_id`. Firmware validates and never treats arbitrary input as unrestricted GPIO control.

### AI / task schemas (defined early, implemented M4+)

- `TaskPlan` / `TaskStep` — validated Pydantic plans
- Tool argument schemas for bounded actions only

---

## 3. Dependencies & integration risks

| Risk | Mitigation |
|---|---|
| Serial port naming differs across OS | Explicit port selection + port listing API; simulation mode default |
| Mock silently mistaken for real hardware | Dashboard and API always surface `connection.type` / `simulation` mode |
| Schema drift between firmware and runtime | Single source of truth under `contracts/`; generate/validate both sides |
| Telemetry DB growth | Retention limits on insert (MVP: simple row count / age prune) |
| LLM untrusted output (later) | Pydantic validation + safety policy before any hardware action |
| Command loss / laptop crash | Firmware watchdog + motor command timeout (M2) |
| Key leakage (later) | keyring only; never return keys from GET `/api/settings/llm` |

**MVP stack dependencies (M1):** FastAPI, Pydantic, aiosqlite/sqlalchemy, pyserial (interface only), Next.js, Tailwind, pytest, vitest.

**Explicitly excluded:** AWS, K8s, Redis, Kafka, MQTT, Docker infra, ROS 2, cloud auth.

---

## 4. Initial repository structure

```text
physical-ai/          # this repo (autobo)
├── apps/dashboard/   # Next.js developer UI
├── runtime/          # FastAPI Physical AI runtime
├── sdk/python/       # Installable SDK (stub in M1)
├── firmware/esp32/   # PlatformIO project (stub in M1)
├── contracts/        # Protocol + shared schemas
├── examples/         # Reference apps (stubs)
├── docs/             # Architecture & setup
├── scripts/          # setup.sh, dev.sh
├── Makefile
├── .env.example
└── README.md
```

Boundaries:

- **Dashboard** talks only to the runtime HTTP/WS API.
- **Runtime** owns devices, storage, hardware adapters, (later) AI/diagnostics/execution.
- **SDK** will wrap the runtime/client API; not imported by the runtime internals.
- **Firmware** speaks only the serial JSON Lines protocol.

---

## 5. Milestone 1 design notes

- Default hardware mode: **simulation**.
- On startup (or first request), seed a simulated rover (`rover-sim-001`) with components: ESP32 controller, distance sensor, left/right motors, encoders, battery.
- Mock adapter emits periodic heartbeat + telemetry over an in-process bus; WebSocket fans out to the dashboard.
- Serial adapter interface exists but is not required for M1 deliverable.
- CORS locked to local dashboard origin; API binds to `127.0.0.1`.
