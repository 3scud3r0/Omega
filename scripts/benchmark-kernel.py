#!/usr/bin/env python3
"""Measure native exact GEMM against mpq on the same inputs and CPU."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from omega_platform.budget import BUILD_BUDGET, COMPILER_BUDGET
from omega_platform.sandbox import c_tool, run, trusted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = ROOT / "testes/kernel/benchmark_gemm.c"
    compiler = shutil.which("cc")
    if not compiler:
        raise RuntimeError("A C compiler is required")
    with tempfile.TemporaryDirectory(prefix="omega-kernel-benchmark-") as tmp:
        folder = Path(tmp)
        binary = folder / "benchmark"
        c_tool([compiler, "-std=c11", "-O3", "-Wall", "-Wextra", "-Wno-unused-function",
                source, "-lgmp", "-o", binary],
               inputs=[ROOT / "testes/kernel", ROOT / "kernel/native", ROOT / "omega_selfhost"],
               output_directory=folder, budget=BUILD_BUDGET, check=True)
        result = run([binary], budget=COMPILER_BUDGET, check=True)
        binary_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
    cpu = "unknown"
    if Path("/proc/cpuinfo").is_file():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    record = {"format": "omega-kernel-gemm-benchmark-1", "architecture": platform.machine(),
              "cpu": cpu, "rows": [json.loads(line) for line in result.stdout.splitlines()],
              "sandboxed": result.sandboxed, "flags": ["-std=c11", "-O3"],
              "compiler": trusted([compiler, "--version"], budget=BUILD_BUDGET, check=True).stdout.splitlines()[0],
              "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "binary_sha256": binary_hash,
              "scope": "same-process GEMM; allocations/output normalization included; parsing/compilation excluded",
              "limitations": "synthetic 32/64 matrices, compact SIMD and wide GMP inputs; not a general neural-network throughput claim"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
