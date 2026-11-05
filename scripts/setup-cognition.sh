#!/usr/bin/env bash
# Minimal CPU prerequisites for Lean crystallization; uses the repository pins.
set -euo pipefail
OMEGA_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OMEGA_TOOLS="${OMEGA_TOOLS_DIR:-$(dirname "$OMEGA_ROOT")/.tools}"
OMEGA_LEAN_ROOT="$OMEGA_TOOLS/lean-4.19.0-linux"
OMEGA_MATHLIB="$OMEGA_TOOLS/mathlib4"
cd "$OMEGA_ROOT"
command -v cc >/dev/null
bash scripts/setup-sandbox.sh
if [[ ! -x "$OMEGA_LEAN_ROOT/bin/lean" ]]; then
  [[ ! -e "$OMEGA_LEAN_ROOT" && "$(uname -s)/$(uname -m)" == Linux/x86_64 ]]
  mkdir -p "$OMEGA_TOOLS"
  OMEGA_DOWNLOAD="$(mktemp -d "$OMEGA_TOOLS/.cognition-lean.XXXXXX")"
  trap 'rm -rf "$OMEGA_DOWNLOAD"' EXIT
  curl --fail --show-error --location --proto '=https' --tlsv1.2 \
    https://github.com/leanprover/lean4/releases/download/v4.19.0/lean-4.19.0-linux.tar.zst \
    -o "$OMEGA_DOWNLOAD/lean.tar.zst"
  (cd "$OMEGA_DOWNLOAD" && printf '%s\n' \
    '6fe3ce97a58f44e2b3567d455b994eacec5bfe9ae7774f2a573444480ba813fe  lean.tar.zst' | sha256sum --check --strict)
  tar --zstd -xf "$OMEGA_DOWNLOAD/lean.tar.zst" -C "$OMEGA_DOWNLOAD"
  mv "$OMEGA_DOWNLOAD/lean-4.19.0-linux" "$OMEGA_LEAN_ROOT"
fi
export PATH="$OMEGA_LEAN_ROOT/bin:$PATH"
export MATHLIB_NO_CACHE_ON_UPDATE=1
[[ "$(lean --version)" == *"version 4.19.0,"* ]]
if [[ ! -d "$OMEGA_MATHLIB/.git" ]]; then
  [[ ! -e "$OMEGA_MATHLIB" ]]
  git clone --depth 1 --branch v4.19.0 https://github.com/leanprover-community/mathlib4.git "$OMEGA_MATHLIB"
fi
[[ "$(git -C "$OMEGA_MATHLIB" rev-parse HEAD)" == c44e0c8ee63ca166450922a373c7409c5d26b00b ]]
git -C "$OMEGA_MATHLIB" diff --quiet
git -C "$OMEGA_MATHLIB" diff --cached --quiet
# Fetch the checked Mathlib cache only when required artifacts are absent.
OMEGA_MODULES=(Mathlib/Tactic/Linarith.lean Mathlib/Data/Real/Sqrt.lean Mathlib/Tactic/FieldSimp.lean
               Mathlib/Algebra/Order/Field/Rat.lean Mathlib/Tactic/Ring.lean
               Mathlib/Tactic/NormNum.lean Mathlib/Tactic/SplitIfs.lean)
OMEGA_MISSING=0
for OMEGA_MODULE in "${OMEGA_MODULES[@]}"; do
  [[ -f "$OMEGA_MATHLIB/.lake/build/lib/lean/${OMEGA_MODULE%.lean}.olean" ]] || OMEGA_MISSING=1
done
if [[ "$OMEGA_MISSING" == 1 ]]; then
  (cd "$OMEGA_MATHLIB" && lake exe cache get "${OMEGA_MODULES[@]}")
fi
mkdir -p formal/tensor/.lake/packages
for OMEGA_DEP in "$OMEGA_MATHLIB" "$OMEGA_MATHLIB"/.lake/packages/*; do
  [[ -d "$OMEGA_DEP" ]] || continue
  OMEGA_DEP_NAME="$(basename "$OMEGA_DEP")"
  if [[ "$OMEGA_DEP" == "$OMEGA_MATHLIB" ]]; then OMEGA_DEP_NAME=mathlib; fi
  if [[ ! -e "formal/tensor/.lake/packages/$OMEGA_DEP_NAME" ]]; then
    ln -s "$OMEGA_DEP" "formal/tensor/.lake/packages/$OMEGA_DEP_NAME"
  fi
done
(cd formal/tensor && lake build Omega.Refinement)
.venv/bin/python - <<'PY'
from omega_selfhost.driver import compiler
from omega_sovereign.hardware import tool
print('Compiler:', compiler())
print('RV64 execution:', tool('qemu-riscv64'))
PY
