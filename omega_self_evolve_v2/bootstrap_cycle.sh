#!/usr/bin/env bash
# Explicit host invocation. With --install --replace-source --commit, adoption
# updates compiler.omega, selects the verified binary and creates a local commit.
# No candidate supplies a shell command and no Git push is performed here.
set -euo pipefail
OMEGA_HYPER_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$OMEGA_HYPER_ROOT"
exec .venv/bin/python -m omega_self_evolve_v2.cli "$@"
