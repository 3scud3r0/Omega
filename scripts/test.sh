#!/usr/bin/env bash
set -euo pipefail
OMEGA_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$OMEGA_ROOT"
export OMEGA_LEAN="${OMEGA_LEAN:-$(dirname "$OMEGA_ROOT")/.tools/lean-4.19.0-linux/bin/lean}"
export NEXTORCH_LEAN="${NEXTORCH_LEAN:-$OMEGA_LEAN}"
export PATH="$(dirname "$OMEGA_LEAN"):$PATH"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
export PYTHONDONTWRITEBYTECODE=1
(cd formal/lean && lake build)
(cd formal/tensor && lake build omega_tensor_kernel Omega)
.venv/bin/python -c 'from omega_selfhost.driver import compiler; compiler()'
exec .venv/bin/python -m pytest -ra "$@"
