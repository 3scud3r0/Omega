#!/usr/bin/env python3
"""Reproducible differential checked-i64 execution on three emitted ISAs."""
from pathlib import Path
import argparse
import json
import operator
import os
import random
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omega_kernel.runtime import request, execute
from omega_kernel.protocol import sha256
from omega_security.encoding import canonical

OPERATORS = {"+": operator.add, "-": operator.sub, "*": operator.mul,
             "==": operator.eq, "!=": operator.ne, "<": operator.lt,
             "<=": operator.le, ">": operator.gt, ">=": operator.ge}


def oracle(op, a, b):
    if op in {"/", "%"}:
        if not b:
            return 2, 0
        if a == -(1 << 63) and b == -1:
            return 1, 0
        quotient = (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)
        remainder = a - quotient * b
        if op == "/" and remainder:
            return 4, 0
        return 0, quotient if op == "/" else remainder
    value = int(OPERATORS[op](a, b))
    return (0, value) if -(1 << 63) <= value < (1 << 63) else (1, 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=int, default=45)
    parser.add_argument("--seed", type=int, default=22130)
    args = parser.parse_args()
    if not 1 <= args.cases <= 100:
        parser.error("case budget 1..100")
    emulators = {"x86_64": None}
    for arch in ("aarch64", "riscv64"):
        path = os.environ.get("OMEGA_KERNEL_QEMU_" + arch.upper()) or shutil.which("qemu-" + arch)
        if not path:
            parser.error("required emulator unavailable: qemu-" + arch)
        emulators[arch] = path
    rng = random.Random(args.seed)
    operations = ["+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">="]
    limits = [-(1 << 63), -(1 << 63) + 1, -(1 << 32), -1, 0, 1,
              1 << 32, (1 << 63) - 2, (1 << 63) - 1]
    records = []
    started = time.monotonic()
    for index in range(args.cases):
        op = operations[index % len(operations)]
        a = rng.choice(limits) if index < 25 else rng.randint(-(1 << 63), (1 << 63) - 1)
        b = rng.choice(limits) if index < 25 else rng.randint(-(1 << 63), (1 << 63) - 1)
        expected = oracle(op, a, b)
        for arch, emulator in emulators.items():
            document = request("compile-source", {"source": "funcao f(a,b) { retornar a" + op + "b; }",
                                                   "architecture": arch})
            actual = execute(document, [a, b], emulator=emulator)
            if (actual["status"], actual["value"]) != expected:
                raise AssertionError((arch, op, a, b, actual, expected))
            records.append({"architecture": arch, "operation": op, "inputs": [a, b],
                            "expected": list(expected), "elf_sha256": actual["elf_sha256"]})
    output = {"format": "omega-kernel-cross-isa-random-1", "seed": args.seed,
              "executions": len(records), "cases": args.cases, "architectures": list(emulators),
              "passed": True, "seconds": time.monotonic() - started, "sandboxed": True,
              "reference": "independent Python integers, explicit exact signed division/remainder",
              "cases_sha256": sha256(canonical(records, max_nodes=100000)), "records": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({k: v for k, v in output.items() if k != "records"}))


if __name__ == "__main__":
    main()
