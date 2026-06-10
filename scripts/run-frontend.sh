#!/usr/bin/env bash
# Start the Vue frontend dev server.
# Run from the repo root: ./scripts/run-frontend.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"

# Try common Node locations if it's not on PATH already.
if ! command -v npm >/dev/null 2>&1; then
  for cand in "$HOME/node/bin" "/opt/homebrew/bin" "/usr/local/bin"; do
    if [ -x "$cand/npm" ]; then
      export PATH="$cand:$PATH"
      break
    fi
  done
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "✗ npm not found. Install Node.js 20+ first." >&2
  exit 1
fi

if [ ! -d node_modules ]; then
  echo "==> installing frontend deps..."
  npm install
fi

exec npm run dev
