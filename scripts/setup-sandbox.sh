#!/usr/bin/env bash
# Ubuntu 22.04's Bubblewrap lacks bounded tmpfs mounts. Build the pinned version.
set -euo pipefail
OMEGA_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OMEGA_TOOLS="${OMEGA_TOOLS_DIR:-$(dirname "$OMEGA_ROOT")/.tools}"
OMEGA_BWRAP_ROOT="$OMEGA_TOOLS/bubblewrap-0.12.0"
if [[ "${OMEGA_BWRAP_FORCE_BUILD:-0}" != 1 ]] && command -v bwrap >/dev/null && [[ "$(bwrap --version)" == 'bubblewrap 0.12.0' ]]; then
  bwrap --help | grep -- '--size' >/dev/null
  exit 0
fi
if [[ -x "$OMEGA_BWRAP_ROOT/bin/bwrap" ]]; then
  [[ "$("$OMEGA_BWRAP_ROOT/bin/bwrap" --version)" == 'bubblewrap 0.12.0' ]]
  exit 0
fi
command -v meson >/dev/null
command -v ninja >/dev/null
command -v pkg-config >/dev/null
mkdir -p "$OMEGA_TOOLS"
OMEGA_BWRAP_TMP="$(mktemp -d "$OMEGA_TOOLS/.bubblewrap.XXXXXX")"
trap 'rm -rf "$OMEGA_BWRAP_TMP"' EXIT
curl --fail --show-error --location --proto '=https' --tlsv1.2 \
  https://github.com/containers/bubblewrap/releases/download/v0.12.0/bubblewrap-0.12.0.tar.xz \
  -o "$OMEGA_BWRAP_TMP/source.tar.xz"
# GitHub release asset digest, independently retrieved through its release API.
(cd "$OMEGA_BWRAP_TMP" && printf '%s\n' \
  '9760d007363e3abba7c747489910f9f82d9fca53ba3bd3282e396fa3c97a3314  source.tar.xz' | sha256sum --check --strict)
tar -xJf "$OMEGA_BWRAP_TMP/source.tar.xz" -C "$OMEGA_BWRAP_TMP"
meson setup "$OMEGA_BWRAP_TMP/build" "$OMEGA_BWRAP_TMP/bubblewrap-0.12.0" \
  --prefix="$OMEGA_BWRAP_ROOT" -Dman=disabled -Dselinux=disabled -Dtests=false -Dbash_completion=disabled -Dzsh_completion=disabled
meson compile -C "$OMEGA_BWRAP_TMP/build" -j 2
meson install -C "$OMEGA_BWRAP_TMP/build"
"$OMEGA_BWRAP_ROOT/bin/bwrap" --version
