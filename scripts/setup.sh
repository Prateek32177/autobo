#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"

echo "==> Physical AI local setup"
echo "    root: $ROOT"

require_cmd python3
require_cmd npm
require_cmd curl

PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
NODE_VERSION="$(node -v 2>/dev/null | sed 's/^v//' || true)"

if ! version_ge "$PY_VERSION" "3.12"; then
  echo "ERROR: Python >= 3.12 required (found $PY_VERSION)" >&2
  exit 1
fi
echo "OK Python $PY_VERSION"

if [[ -z "$NODE_VERSION" ]]; then
  echo "ERROR: Node.js not found (need >= 20)" >&2
  exit 1
fi
if ! version_ge "$NODE_VERSION" "20"; then
  echo "ERROR: Node.js >= 20 required (found $NODE_VERSION)" >&2
  exit 1
fi
echo "OK Node $NODE_VERSION"

mkdir -p "$ROOT/runtime/data" "$LOG_DIR" "$RUN_DIR"

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Created $ROOT/.env from .env.example"
else
  echo "Keeping existing $ROOT/.env"
fi

if [[ ! -f "$ROOT/apps/dashboard/.env.local" ]]; then
  cp "$ROOT/apps/dashboard/.env.example" "$ROOT/apps/dashboard/.env.local"
  echo "Created apps/dashboard/.env.local"
else
  echo "Keeping existing apps/dashboard/.env.local"
fi

echo "==> Runtime virtualenv + dependencies"
cd "$ROOT/runtime"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -e ".[dev]"
pip install -e "$ROOT/sdk/python"

echo "==> Initialize SQLite"
cd "$ROOT"
PYTHONPATH="$ROOT" "$ROOT/runtime/.venv/bin/python" - <<'PY'
from pathlib import Path
import asyncio
from physical_ai.storage.database import Database

db_path = Path("runtime/data/physical_ai.db")

async def main() -> None:
    db = Database(db_path)
    await db.connect()
    await db.close()
    print(f"SQLite ready at {db_path.resolve()}")

asyncio.run(main())
PY

echo "==> Dashboard dependencies"
cd "$ROOT/apps/dashboard"
npm install

echo "==> Setup complete"
echo "Next:"
echo "  ./scripts/start.sh"
echo "  ./scripts/doctor.sh"
echo "Dashboard: $DASHBOARD_URL"
echo "Runtime:   $RUNTIME_URL"
