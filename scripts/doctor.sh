#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"

FAILS=0

ok() { echo "OK  $*"; }
warn() { echo "WARN $*"; }
fail() { echo "FAIL $*"; FAILS=$((FAILS + 1)); }

echo "==> Physical AI doctor"
echo "    root: $ROOT"

if command -v python3 >/dev/null; then
  PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
  SHORT="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if version_ge "$SHORT" "3.12"; then
    ok "Python $PY_VERSION"
  else
    fail "Python >= 3.12 required (found $PY_VERSION)"
  fi
else
  fail "python3 not found"
fi

if command -v node >/dev/null; then
  NODE_VERSION="$(node -v | sed 's/^v//')"
  if version_ge "$NODE_VERSION" "20"; then
    ok "Node $NODE_VERSION"
  else
    fail "Node >= 20 required (found $NODE_VERSION)"
  fi
else
  fail "node not found"
fi

require_cmd npm && ok "npm $(npm -v)" || fail "npm missing"
require_cmd curl && ok "curl available" || fail "curl missing"

if [[ -x "$ROOT/runtime/.venv/bin/python" ]]; then
  ok "runtime venv present"
  if "$ROOT/runtime/.venv/bin/python" -c "import fastapi, serial, aiosqlite" 2>/dev/null; then
    ok "runtime Python dependencies importable"
  else
    fail "runtime deps missing — run ./scripts/setup.sh"
  fi
  if "$ROOT/runtime/.venv/bin/python" -c "import physical_ai_sdk" 2>/dev/null; then
    ok "physical_ai_sdk importable"
  else
    fail "SDK not installed — run ./scripts/setup.sh"
  fi
else
  fail "runtime/.venv missing — run ./scripts/setup.sh"
fi

if [[ -d "$ROOT/apps/dashboard/node_modules" ]]; then
  ok "dashboard node_modules present"
else
  fail "dashboard dependencies missing — run ./scripts/setup.sh"
fi

if [[ -f "$ROOT/.env" ]]; then
  ok ".env present"
else
  warn ".env missing (will be created by setup from .env.example)"
fi

if [[ -f "$ROOT/apps/dashboard/.env.local" ]]; then
  ok "dashboard .env.local present"
else
  warn "apps/dashboard/.env.local missing"
fi

DB_PATH="$ROOT/runtime/data/physical_ai.db"
if [[ -f "$DB_PATH" ]]; then
  ok "SQLite database exists ($DB_PATH)"
else
  warn "SQLite DB not created yet (created on setup/start)"
fi

if curl -sf "$RUNTIME_URL/health" >/dev/null 2>&1; then
  ok "backend /health reachable at $RUNTIME_URL"
else
  fail "backend not reachable at $RUNTIME_URL/health — run ./scripts/start.sh"
fi

if curl -sf "$RUNTIME_URL/ready" >/dev/null 2>&1; then
  READY_JSON="$(curl -s "$RUNTIME_URL/ready")"
  if echo "$READY_JSON" | grep -q '"ready": true\|"ready":true'; then
    ok "backend /ready reports ready"
  else
    fail "backend /ready not ready: $READY_JSON"
  fi
else
  fail "backend /ready not reachable"
fi

if curl -sf "$DASHBOARD_URL" >/dev/null 2>&1; then
  ok "dashboard reachable at $DASHBOARD_URL"
else
  fail "dashboard not reachable at $DASHBOARD_URL — run ./scripts/start.sh"
fi

# Serial enumeration capability (does not require a connected device)
if "$ROOT/runtime/.venv/bin/python" - <<'PY' 2>/dev/null
from physical_ai.hardware.transport.serial import list_serial_ports
ports = list_serial_ports()
print(f"ports={len(ports)}")
PY
then
  ok "serial port enumeration works (ESP32 not required to start)"
else
  warn "serial enumeration failed — pyserial may be missing or restricted"
fi

# LLM config availability without requiring a key
if curl -sf "$RUNTIME_URL/api/meta" >/dev/null 2>&1; then
  META="$(curl -s "$RUNTIME_URL/api/meta")"
  if echo "$META" | grep -q '"ai_ready": false\|"ai_ready":false'; then
    ok "LLM not required yet (ai_ready=false) — no API key needed for simulation"
  else
    ok "runtime meta reachable"
  fi
else
  warn "could not read /api/meta"
fi

echo ""
if [[ "$FAILS" -eq 0 ]]; then
  echo "Doctor result: all critical checks passed"
  exit 0
fi
echo "Doctor result: $FAILS failure(s) — see messages above"
exit 1
