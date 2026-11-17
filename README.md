# Physical AI

Local-first developer platform for connecting physical hardware, observing component health, diagnosing failures, and running bounded AI-driven physical tasks.

**Current milestone:** 2 — Hardware architecture (transport / protocol / components) + ESP32 path

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

## What Milestone 2 adds (preserves M1)

1. `TransportAdapter` (USB serial + in-memory for tests/mock)
2. JSON Lines `ProtocolSession` (handshake, correlation, malformed handling)
3. Real `ComponentAdapter`s for rover parts + `ComponentRegistry`
4. `CapabilityRegistry` + dynamic AI tool generation
5. Safety validator + action executor pipeline
6. `Esp32HardwareAdapter` + firmware peer in `firmware/esp32`
7. Mock still default; uses same component/capability contracts (not USB serial)

### Milestone 1 still works

Simulated rover seed, dashboard telemetry, localhost FastAPI, SQLite, explicit simulation mode.

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
