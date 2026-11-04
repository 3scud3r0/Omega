#!/usr/bin/env bash
# Optional RISC Zero integration: local CPU prover and static standalone verifier.
# Requires rustup, C++17 host compiler and network access for checksum-locked
# Cargo packages plus the RISC Zero recursion artifact. Does not install CUDA.
set -euo pipefail
OMEGA_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$OMEGA_ROOT"
command -v rustup >/dev/null || { echo 'rustup is required (https://rustup.rs)' >&2; exit 1; }
rustup toolchain install 1.90.0 --profile minimal --no-self-update
rustup +1.90.0 target add x86_64-unknown-linux-musl
export CARGO_BUILD_JOBS=2
export CARGO_TARGET_DIR="$OMEGA_ROOT/build/risc0"
# Never use RISC0_DEV_MODE, fake receipts or DOCS_RS to bypass the prover build.
cargo +1.90.0 build --release --locked --manifest-path omega_zk/risc0/Cargo.toml
cargo +1.90.0 build --release --locked --no-default-features \
  --target x86_64-unknown-linux-musl --manifest-path omega_zk/risc0/Cargo.toml
printf '%s\n' "Prover: $CARGO_TARGET_DIR/release/omega-risc0" \
  "Verifier: $CARGO_TARGET_DIR/x86_64-unknown-linux-musl/release/omega-risc0"
