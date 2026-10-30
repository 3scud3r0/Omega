"""Explicit command line for the three bounded native kernel candidates."""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys

from . import runtime
from .amalgamation import extract, inspect
from .certificates import create_tensor_certificate, verify_tensor_certificate
from .protocol import elf_bytes, read_document


def _json(value):
    if type(value) is Fraction:
        return str(value)
    raise TypeError("Non-JSON kernel result")


def _write_json(value, destination=None):
    text = json.dumps(value, indent=2, ensure_ascii=False, default=_json) + "\n"
    if destination:
        with Path(destination).open("x", encoding="utf-8") as stream:
            stream.write(text)
    else:
        sys.stdout.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    build = sub.add_parser("build", help="build native adapters")
    build.add_argument("kind", choices=["logic", "tensor", "workbench"])
    build.add_argument("--sanitize", action="store_true")
    call = sub.add_parser("request", help="execute a data-only request under isolation")
    call.add_argument("operation", choices=sorted(runtime.NATIVE_OPERATIONS | runtime.OMEGA_OPERATIONS))
    call.add_argument("input", type=Path)
    call.add_argument("--sanitize", action="store_true")
    call.add_argument("--output", type=Path)
    compile_parser = sub.add_parser("compile", help="pure Omega function -> direct Linux ELF")
    compile_parser.add_argument("source", type=Path)
    compile_parser.add_argument("--architecture", choices=["x86_64", "aarch64", "riscv64"], default="x86_64")
    compile_parser.add_argument("--output", type=Path, required=True)
    execute = sub.add_parser("run", help="compile and sandbox an i64 pure function")
    execute.add_argument("source", type=Path)
    execute.add_argument("values", nargs="*", type=int)
    execute.add_argument("--architecture", choices=["x86_64", "aarch64", "riscv64"], default="x86_64")
    execute.add_argument("--emulator", type=Path)
    bundle = sub.add_parser("extract", help="extract inert mixed-language source frames")
    bundle.add_argument("bundle", type=Path)
    bundle.add_argument("destination", type=Path)
    inspect_parser = sub.add_parser("inspect", help="inspect source hashes")
    inspect_parser.add_argument("bundle", type=Path)
    certify = sub.add_parser("certify-tensor", help="run arithmetic and check its reconstructed statement")
    certify.add_argument("input", type=Path)
    certify.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify-tensor", help="bind and check an arithmetic certificate")
    verify.add_argument("certificate", type=Path)
    verify.add_argument("--reference", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "build":
        print(runtime.build(args.kind, diagnostic=args.sanitize))
    elif args.action == "request":
        _write_json(runtime.request(args.operation, read_document(args.input), diagnostic=args.sanitize), args.output)
    elif args.action in {"compile", "run"}:
        with args.source.open(encoding="utf-8") as stream:
            source = stream.read(16385)
        result = runtime.request("compile-source", {"source": source, "architecture": args.architecture})
        if args.action == "compile":
            data = elf_bytes(result)
            with args.output.open("xb") as stream:
                stream.write(data)
            args.output.chmod(0o500)
            _write_json(result, str(args.output) + ".kernel.json")
            _write_json({"elf": str(args.output), "bytes": len(data),
                         "sha256": runtime.sha256(data), "architecture": args.architecture,
                         "verified": False, "external_assembler": False, "external_linker": False})
        else:
            _write_json(runtime.execute(result, args.values, emulator=args.emulator))
    elif args.action == "extract":
        _write_json(extract(args.bundle.read_bytes(), args.destination))
    elif args.action == "inspect":
        manifest, _, _ = inspect(args.bundle.read_bytes())
        _write_json(manifest)
    elif args.action == "certify-tensor":
        packet = read_document(args.input)
        result = runtime.request("tensor", packet)
        certificate = create_tensor_certificate(packet, result)
        outcome = verify_tensor_certificate(certificate)
        if not outcome["accepted"]:
            _write_json(outcome)
            return 1
        _write_json(certificate, args.output)
        _write_json(outcome)
    elif args.action == "verify-tensor":
        outcome = verify_tensor_certificate(read_document(args.certificate), reference=args.reference)
        _write_json(outcome)
        return 0 if outcome["accepted"] else 1
    return 0
