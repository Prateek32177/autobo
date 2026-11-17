# Physical AI

Local-first developer platform for connecting physical hardware, observing component health, diagnosing failures, and running bounded AI-driven physical tasks.

**Local deployment only.** The hardware runtime is not deployed to Vercel, AWS, or any cloud host.

## Architecture overview

```text
Developer laptop
├── Next.js dashboard     http://localhost:3000
├── FastAPI runtime       http://127.0.0.1:8000
│   ├── Device / component / capability registries
│   ├── Mock simulation + ESP32 serial adapters
│   └── SQLite (runtime/data/physical_ai.db)
└── USB serial (optional ESP32) — not required to start
```

## Development status

| Area | Status |
|---|---|
| Local setup / start / stop / doctor | **Implemented** |
| Simulated rover telemetry + health | **Implemented** |
| Dashboard Overview + Devices | **Implemented** (live backend) |
| Transport / protocol / component adapters | **Implemented** |
| Diagnostics event API | **Implemented** (rules engine pending M3) |
| AI playground / LLM settings | **Pending** (M4) — UI states this honestly |
| Physical ESP32 end-to-end on hardware | **Prepared** (firmware + serial path); needs a board to demo |

## Prerequisites

- Python **3.12+**
- Node.js **20+** and npm
- curl
- macOS / Linux (Windows WSL should work; native Windows not primary)

## One-command setup

```bash
./scripts/setup.sh
```

Idempotent. Creates venv, installs runtime + SDK + dashboard deps, initializes SQLite, and writes `.env` / `.env.local` **only if missing** (never overwrites).

## Start / stop / status

```bash
./scripts/start.sh    # runtime + dashboard
./scripts/status.sh
./scripts/stop.sh     # only processes started by start.sh
./scripts/doctor.sh   # environment + connectivity checks
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| Runtime health | http://127.0.0.1:8000/health |
| Runtime ready | http://127.0.0.1:8000/ready |
| OpenAPI | http://127.0.0.1:8000/docs |

Logs: `logs/runtime.log`, `logs/dashboard.log`  
PIDs: `.run/runtime.pid`, `.run/dashboard.pid`

## Simulation workflow

1. `./scripts/setup.sh && ./scripts/start.sh`
2. Open the dashboard.
3. Confirm **Backend: online** and the **SIMULATION** banner.
4. Inspect `rover-sim-001` components, live telemetry, and capabilities.
5. Use Devices connect/disconnect and Emergency stop.
6. Diagnostics shows the events API (often empty until M3 rules fire).

No ESP32 is required.

## Environment variables

Copy from [`.env.example`](.env.example). Important keys:

| Variable | Default | Purpose |
|---|---|---|
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Runtime bind (localhost) |
| `SEED_SIMULATED_DEVICE` | `true` | Auto-seed mock rover |
| `SIMULATED_DEVICE_ID` | `rover-sim-001` | Seeded device id |
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | Dashboard → runtime |

**Do not put LLM API keys in `.env`.** Keys will use OS keyring in Milestone 4 and must never reach browser storage.

## Python SDK

```bash
# installed by setup into runtime/.venv
source runtime/.venv/bin/activate
python -c "from physical_ai_sdk import RuntimeClient; print(RuntimeClient().health())"
```

See [docs/sdk_quickstart.md](docs/sdk_quickstart.md).

Runtime package (`physical_ai`) ≠ SDK package (`physical_ai_sdk`).

## LLM configuration

Not required for local simulation. `/api/meta` reports `ai_ready: false`. Settings page shows that no LLM is configured.

## Virtual ESP32 (serial path without a board)

Exercises the **real** `SerialHardwareAdapter` path over a socat PTY pair (not MockHardwareAdapter):

```bash
brew install socat          # once
./scripts/virtual_esp32_start.sh
./scripts/start.sh
# Register/connect a device with connection.type=serial and port=.run/ttyVESP32-host
./scripts/virtual_esp32_stop.sh
```

Docs: [firmware/virtual_esp32/README.md](firmware/virtual_esp32/README.md)

## ESP32 preparation (no board required to start)

- `pyserial` installed; `GET /api/hardware/ports` enumerates ports.
- Firmware project: `firmware/esp32` (PlatformIO) — handshake, telemetry, commands, watchdog.
- Docs: [docs/hardware_setup.md](docs/hardware_setup.md), [docs/firmware_protocol.md](docs/firmware_protocol.md).

Physical connection and upload instructions stay optional until you have hardware.

## Tests

```bash
make test              # runtime + dashboard + SDK
make build-dashboard   # Next.js production build
./scripts/doctor.sh    # with stack running
```

## Troubleshooting

| Symptom | Action |
|---|---|
| Port 8000/3000 in use | `./scripts/stop.sh`; if foreign process, free the port or set `PHYSICAL_AI_PORT` / `PHYSICAL_AI_DASHBOARD_PORT` |
| Backend offline in UI | `./scripts/status.sh` and check `logs/runtime.log` |
| Setup fails on Python | Install Python 3.12+ |
| Serial ports empty | Normal without devices; still OK for simulation |
| Doctor fails SDK import | Re-run `./scripts/setup.sh` |

## Docs

- [docs/deployment.md](docs/deployment.md) — deployment assessment
- [docs/architecture.md](docs/architecture.md) — product architecture
- [docs/m2_hardware_architecture.md](docs/m2_hardware_architecture.md) — hardware layers
