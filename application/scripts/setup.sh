#!/usr/bin/env bash
# One-shot first-time setup: Rust toolchain → uv → Python 3.10 venv → libriichi.so
# Run from the repo root: ./application/scripts/setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "==> 1/4  installing Rust (rustup)..."
if ! command -v cargo >/dev/null 2>&1; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --default-toolchain stable --profile minimal
fi
. "$HOME/.cargo/env"

echo "==> 2/4  installing uv (Python version manager)..."
if [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
UV="$HOME/.local/bin/uv"

echo "==> 3/4  creating Python 3.10 venv (source_code/.venv) with deps..."
"$UV" python install 3.10
"$UV" venv --python 3.10 source_code/.venv
"$UV" pip install --python source_code/.venv/bin/python \
    torch numpy toml tqdm fastapi 'uvicorn[standard]' websockets

echo "==> 4/4  building libriichi.so..."
PYO3_PYTHON="$ROOT/source_code/.venv/bin/python" \
  cargo build --manifest-path source_code/Cargo.toml -p libriichi --lib --release

# Resulting binary: Linux → libriichi.so, macOS → libriichi.dylib, Windows → riichi.dll
case "$(uname -s)" in
  Darwin)  cp source_code/target/release/libriichi.dylib source_code/mortal/libriichi.so ;;
  Linux)   cp source_code/target/release/libriichi.so    source_code/mortal/libriichi.so ;;
  MINGW*|MSYS*|CYGWIN*) cp source_code/target/release/riichi.dll source_code/mortal/libriichi.pyd ;;
  *) echo "unknown platform $(uname -s); copy the cdylib manually into source_code/mortal/" ;;
esac

echo
echo "✓ setup done."
echo "  Run backend:  ./application/scripts/run-backend.sh"
echo "  Run frontend: ./application/scripts/run-frontend.sh"
