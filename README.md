# Physical AI

Local-first developer platform for connecting physical hardware, observing component health, diagnosing failures, and running bounded AI-driven physical tasks.

**Current milestone:** 1 — Local runtime foundation (simulated rover)

## Architecture (MVP)

```text
Dashboard (Next.js)  →  Runtime (FastAPI)  →  Mock / Serial hardware adapter  →  ESP32
                                      ↓
                                   SQLite
```

See [docs/architecture.md](docs/architecture.md) for the phased plan, shared contracts, and risks.

## Quick start

### Prerequisites

- Python 3.12+
- Node.js 20+
- npm

### Setup

```bash
./scripts/setup.sh
# or: make setup
```

### Run locally

```bash
./scripts/dev.sh
# or: make dev
```

- Dashboard: http://127.0.0.1:3000  
- Runtime API: http://127.0.0.1:8000  
- OpenAPI docs: http://127.0.0.1:8000/docs  

Or run processes separately:

```bash
make runtime     # terminal 1
make dashboard   # terminal 2
```

### Tests

```bash
make test
```

## What Milestone 1 demonstrates

1. FastAPI runtime bound to **localhost**
2. SQLite persistence for devices, components, telemetry
3. Device registry with a seeded **simulated** rover (`rover-sim-001`)
4. Mock hardware adapter emitting heartbeat + telemetry
5. Dashboard Overview / Devices showing component health and live sample telemetry
6. Explicit **simulation** mode (never silently mistaken for real hardware)
7. Serial adapter interface stubbed for Milestone 2 (ESP32)

## Repository layout

```text
apps/dashboard/   Next.js developer UI
runtime/          FastAPI Physical AI runtime
contracts/        Shared Pydantic schemas + serial protocol
sdk/python/       Installable SDK (stub)
firmware/esp32/   PlatformIO firmware (stub until M2)
docs/             Architecture and protocol docs
scripts/          setup.sh, dev.sh
```

## Hardware mode

| Mode | Status in M1 |
|---|---|
| `simulation` | Fully working (default) |
| `serial` | API-visible stub; returns 501 until Milestone 2 |

The dashboard always shows the active hardware mode banner.

## Explicitly out of scope (MVP)

Cloud control planes, fleet management, ROS 2, MQTT, Docker/K8s infrastructure, multi-tenancy, and general-purpose autonomous navigation.
