#!/usr/bin/env bash
# Reproducible native compiler + exact tensor kernel, pinned to Lean/Mathlib 4.19.
set -euo pipefail
OMEGA_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OMEGA_TOOLS="${OMEGA_TOOLS_DIR:-$(dirname "$OMEGA_ROOT")/.tools}"
OMEGA_LEAN_ROOT="$OMEGA_TOOLS/lean-4.19.0-linux"
export PATH="$OMEGA_LEAN_ROOT/bin:$PATH"
export MATHLIB_NO_CACHE_ON_UPDATE=1
cd "$OMEGA_ROOT"
command -v cc >/dev/null
OMEGA_CHECK_DIR="$(mktemp -d)"
trap 'rm -rf "$OMEGA_CHECK_DIR"' EXIT
printf '#include <gmp.h>\nint main(void){mpq_t x;mpq_init(x);mpq_clear(x);return 0;}\n' \
  | cc -x c - -lgmp -o "$OMEGA_CHECK_DIR/gmp-check"
"$OMEGA_CHECK_DIR/gmp-check"
printf '#include <openssl/evp.h>\nint main(void){return EVP_sha256()==0;}\n' \
  | cc -x c - -lcrypto -o "$OMEGA_CHECK_DIR/crypto-check"
"$OMEGA_CHECK_DIR/crypto-check"
lean --version
[[ "$(lean --version)" == *"version 4.19.0,"* ]] || { echo 'Lean 4.19.0 is required' >&2; exit 1; }
OMEGA_MATHLIB="$OMEGA_TOOLS/mathlib4"
if [[ ! -d "$OMEGA_MATHLIB/.git" ]]; then
  [[ ! -e "$OMEGA_MATHLIB" ]] || { echo 'Refusing to overwrite existing Mathlib directory' >&2; exit 1; }
  git clone --depth 1 --branch v4.19.0 https://github.com/leanprover-community/mathlib4.git "$OMEGA_MATHLIB"
fi
[[ "$(git -C "$OMEGA_MATHLIB" rev-parse HEAD)" == c44e0c8ee63ca166450922a373c7409c5d26b00b ]] || {
  echo 'Mathlib must use the pinned 4.19.0 commit; existing checkout was preserved.' >&2; exit 1;
}
git -C "$OMEGA_MATHLIB" diff --quiet
git -C "$OMEGA_MATHLIB" diff --cached --quiet
mkdir -p formal/tensor/.lake/packages
if [[ ! -e formal/tensor/.lake/packages/mathlib ]]; then
  ln -s "$OMEGA_MATHLIB" formal/tensor/.lake/packages/mathlib
fi
# Reuse already prepared dependency caches; never replace existing directories.
for OMEGA_DEP in "$OMEGA_MATHLIB"/.lake/packages/*; do
  [[ -d "$OMEGA_DEP" ]] || continue
  OMEGA_DEP_NAME="$(basename "$OMEGA_DEP")"
  if [[ ! -e "formal/tensor/.lake/packages/$OMEGA_DEP_NAME" ]]; then
    ln -s "$OMEGA_DEP" "formal/tensor/.lake/packages/$OMEGA_DEP_NAME"
  fi
done
(cd formal/tensor && lake build omega_tensor_kernel Omega ScienceAxioms)
.venv/bin/python - <<'PY'
from omega_selfhost.driver import compiler
print('Self-hosted compiler:', compiler())
PY
