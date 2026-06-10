#!/usr/bin/env bash
# Start the Mortal gameplay backend.
# Run from the repo root: ./scripts/run-backend.sh [port]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${1:-8001}"

if [ ! -x "Mortal/.venv/bin/python" ]; then
  echo "✗ Mortal/.venv not found. Run ./scripts/setup.sh first." >&2
  exit 1
fi

if [ ! -f "Mortal/mortal/libriichi.so" ] && [ ! -f "Mortal/mortal/libriichi.pyd" ]; then
  echo "✗ libriichi extension not built. Run ./scripts/setup.sh first." >&2
  exit 1
fi

PYTHONPATH=backend/src exec Mortal/.venv/bin/python -m mortal_play \
  --host 127.0.0.1 --port "$PORT"
