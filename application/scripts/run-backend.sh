#!/usr/bin/env bash
# Start the Mortal gameplay backend.
# Run from the repo root: ./application/scripts/run-backend.sh [port]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

PORT="${1:-8001}"

if [ ! -x "source_code/.venv/bin/python" ]; then
  echo "✗ source_code/.venv not found. Run ./application/scripts/setup.sh first." >&2
  exit 1
fi

if [ ! -f "source_code/mortal/libriichi.so" ] && [ ! -f "source_code/mortal/libriichi.pyd" ]; then
  echo "✗ libriichi extension not built. Run ./application/scripts/setup.sh first." >&2
  exit 1
fi

PYTHONPATH=application/backend/src exec source_code/.venv/bin/python -m mortal_play \
  --host 127.0.0.1 --port "$PORT"
