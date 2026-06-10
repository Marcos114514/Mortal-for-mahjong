#!/usr/bin/env bash
# Build the Mortal gameplay backend image, auto-selecting CPU/CUDA by platform.
#
#   - macOS               -> CPU build (Docker on Mac can't access the GPU)
#   - Linux/Windows + nvidia-smi present -> CUDA build
#   - otherwise           -> CPU build
#
# Override manually:  TORCH_VARIANT=cuda ./build-play.sh
set -euo pipefail

cd "$(dirname "$0")"

variant="${TORCH_VARIANT:-}"

if [ -z "$variant" ]; then
  os="$(uname -s)"
  if [ "$os" = "Darwin" ]; then
    variant="cpu"
  elif command -v nvidia-smi >/dev/null 2>&1; then
    variant="cuda"
  else
    variant="cpu"
  fi
fi

echo "==> Platform: $(uname -s), building with TORCH_VARIANT=$variant"
docker build -f Dockerfile.play --build-arg "TORCH_VARIANT=$variant" -t mortal-play .

echo "==> Done. Run with:"
if [ "$variant" = "cuda" ]; then
  echo "    docker run --gpus all -p 8000:8000 -v \$PWD/mnt:/mnt mortal-play"
else
  echo "    docker run -p 8000:8000 -v \$PWD/mnt:/mnt mortal-play"
fi
