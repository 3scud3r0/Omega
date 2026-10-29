#!/usr/bin/env bash
# Optional compile-only CUDA SDK, with pinned wheel SHA256 verification.
set -euo pipefail
OMEGA_HYPER_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OMEGA_HYPER_TOOLS="${OMEGA_TOOLS_DIR:-$(dirname "$OMEGA_HYPER_ROOT")/.tools}"
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || { echo 'Pinned CUDA SDK targets Linux x86_64.' >&2; exit 1; }
"$OMEGA_HYPER_ROOT/.venv/bin/python" -m pip install --require-hashes --no-deps --upgrade \
  --target "$OMEGA_HYPER_TOOLS/cuda-py" -r "$OMEGA_HYPER_ROOT/requirements/cuda-linux-x86_64.lock"
"$OMEGA_HYPER_TOOLS/cuda-py/nvidia/cu13/bin/nvcc" --version
