#!/usr/bin/env bash
# Reproducible Linux x86_64 / Python 3.12 CPU + Orange + Lean environment.
set -euo pipefail
OMEGA_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OMEGA_TOOLS="${OMEGA_TOOLS_DIR:-$(dirname "$OMEGA_ROOT")/.tools}"
cd "$OMEGA_ROOT"
python3 -c 'import sys; assert sys.version_info[:2] == (3, 12), "The supplied lock requires Python 3.12"'
python3 -m venv .venv
PYTHON_BIN="$OMEGA_ROOT/.venv/bin/python"
"$PYTHON_BIN" -m pip install --cache-dir "$(dirname "$OMEGA_ROOT")/.cache/pip" \
  --index-url https://download.pytorch.org/whl/cpu 'torch==2.5.1'
"$PYTHON_BIN" -m pip install --cache-dir "$(dirname "$OMEGA_ROOT")/.cache/pip" -r requirements/cpu-py312.lock
"$PYTHON_BIN" -m pip install --no-deps --no-build-isolation -e .
LEAN_ROOT="$OMEGA_TOOLS/lean-4.19.0-linux"
if [[ ! -x "$LEAN_ROOT/bin/lean" ]]; then
  [[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || {
    echo 'Pinned Lean archive requires Linux x86_64.' >&2; exit 1;
  }
  [[ ! -e "$LEAN_ROOT" ]] || { echo "Refusing to overwrite $LEAN_ROOT" >&2; exit 1; }
  mkdir -p "$OMEGA_TOOLS"
  OMEGA_DOWNLOAD="$(mktemp -d "$OMEGA_TOOLS/.lean-download.XXXXXX")"
  trap 'rm -rf "$OMEGA_DOWNLOAD"' EXIT
  curl --fail --show-error --location --proto '=https' --tlsv1.2 \
    https://github.com/leanprover/lean4/releases/download/v4.19.0/lean-4.19.0-linux.tar.zst \
    -o "$OMEGA_DOWNLOAD/lean.tar.zst"
  (cd "$OMEGA_DOWNLOAD" && printf '%s\n' \
    '6fe3ce97a58f44e2b3567d455b994eacec5bfe9ae7774f2a573444480ba813fe  lean.tar.zst' | sha256sum --check --strict)
  tar --zstd -xf "$OMEGA_DOWNLOAD/lean.tar.zst" -C "$OMEGA_DOWNLOAD"
  mv "$OMEGA_DOWNLOAD/lean-4.19.0-linux" "$LEAN_ROOT"
fi
"$LEAN_ROOT/bin/lean" --version
export PATH="$LEAN_ROOT/bin:$PATH"
(cd formal/lean && lake build)
"$PYTHON_BIN" -m pip check
bash scripts/setup-native.sh
