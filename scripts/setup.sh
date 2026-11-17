#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Setting up Physical AI (Milestone 1)"

echo "==> Python runtime"
cd "$ROOT/runtime"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

echo "==> Dashboard"
cd "$ROOT/apps/dashboard"
if [[ ! -f .env.local ]]; then
  cp .env.example .env.local
fi
npm install

echo "==> Done"
echo "Start with: make dev   (or ./scripts/dev.sh)"
