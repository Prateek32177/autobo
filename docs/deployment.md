# Local deployment assessment & plan

## What already runs

| Area | Status |
|---|---|
| FastAPI runtime + SQLite seed of simulated rover | Works |
| Mock telemetry / WebSocket | Works |
| Device/hardware REST APIs | Works |
| Next.js Overview + Devices (live API) | Works |
| Pytest (31) + Vitest + `next build` | Works |
| `scripts/setup.sh` / `dev.sh` | Partial |

## Gaps blocking one-command use

1. **Setup incomplete** — no Python/Node version checks, no SDK install, no data/log dirs, no root `.env`, no explicit DB init.
2. **No start/stop/status/doctor** — only `dev.sh`; no PID tracking, port checks, or logs.
3. **No `/ready`** — only `/api/health` (liveness-ish).
4. **SDK stub** — not installable usefully; package name would collide with runtime `physical_ai`.
5. **Dashboard** — no persistent backend connection indicator; Diagnostics/Tasks/Settings are placeholders (honest, but should show live API reachability where possible).
6. **Docs** — README still mentions serial 501 in places; missing troubleshooting / status matrix.
7. **Env loading** — settings look for `.env` relative to CWD, not reliably the repo root.

## Plan

1. Harden `setup.sh`; add `start.sh` / `stop.sh` / `status.sh` / `doctor.sh` with `.run/` PIDs and `logs/`.
2. Add `/health` + `/ready`; keep `/api/health` for compatibility.
3. Ship `physical_ai_sdk` client (editable) + smoke test.
4. Dashboard: backend status in shell; wire diagnostics list to real events API; clarify unimplemented pages.
5. Root `.env.example`, Makefile targets, README rewrite for clone → setup → start.
6. Run full verification suite.

## Non-goals

Cloud/Vercel/Docker/K8s, full ESP32 physical bring-up, new product features.
