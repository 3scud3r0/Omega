#!/usr/bin/env bash
# Optional Debian 13 amd64 RTL simulator, installed without root privileges.
# apt authenticates signed repository metadata and package SHA256 checksums.
set -euo pipefail
OMEGA_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OMEGA_TOOLS="${OMEGA_TOOLS_DIR:-$(dirname "$OMEGA_ROOT")/.tools}"
if command -v iverilog >/dev/null; then iverilog -V; exit 0; fi
if [[ -x "$OMEGA_TOOLS/iverilog/usr/bin/iverilog" ]]; then
  "$OMEGA_TOOLS/iverilog/usr/bin/iverilog" -B "$OMEGA_TOOLS/iverilog/usr/lib/x86_64-linux-gnu/ivl" -g2012 -s rational_alu -o /tmp/omega-qpu-setup "$OMEGA_ROOT"/hardware/qpu/*.sv
  exit 0
fi
[[ "$(dpkg --print-architecture)" == amd64 ]] || { echo 'Local simulator package requires Debian amd64.' >&2; exit 1; }
OMEGA_APT="$OMEGA_TOOLS/apt-qpu"
mkdir -p "$OMEGA_APT/lists/partial" "$OMEGA_APT/cache/archives/partial" "$OMEGA_APT/packages"
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main' > "$OMEGA_APT/sources.list"
OMEGA_APT_ARGS=(-o "Dir::State::lists=$OMEGA_APT/lists" -o "Dir::Cache=$OMEGA_APT/cache" -o "Dir::Etc::sourcelist=$OMEGA_APT/sources.list" -o Dir::Etc::sourceparts=-)
apt-get "${OMEGA_APT_ARGS[@]}" update
(cd "$OMEGA_APT/packages" && apt-get "${OMEGA_APT_ARGS[@]}" download 'iverilog=12.0-2+b1')
OMEGA_EXTRACT="$(mktemp -d "$OMEGA_TOOLS/.iverilog.XXXXXX")"
trap 'rm -rf "$OMEGA_EXTRACT"' EXIT
dpkg-deb -x "$OMEGA_APT/packages/iverilog_12.0-2+b1_amd64.deb" "$OMEGA_EXTRACT"
mv "$OMEGA_EXTRACT" "$OMEGA_TOOLS/iverilog"
trap - EXIT
bash "$OMEGA_ROOT/scripts/setup-qpu.sh"
