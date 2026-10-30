"""Deterministic mixed-language source distribution with inert foreign sections.

The executable Omega prefix is a namespace-resolved import closure. Original
modules and C/Python support are stored as hash-bound comment frames; extracting
them does not compile, import or execute any embedded source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile

from omega.modules import link
from omega_security.encoding import canonical, decode

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "omega_kernel.omega"
MARKER = "# OMEGA-KERNEL-SOURCES-BEGIN\n"
HEADER = "# OMEGA-KERNEL-MANIFEST "
FILE = "# OMEGA-KERNEL-FILE "
END = "# OMEGA-KERNEL-FILE-END\n"
MAX_BYTES = 12 * 1024**2


def _pretty(source):
    """Format linked code lexically, without touching string literals.

    This adds normal block/statement layout, not generated dummy functions or
    padding. The compiler still receives exactly the same tokens.
    """
    lines = []
    line = ""
    level = 0
    quoted = False
    escaped = False
    for char in source:
        if quoted:
            line += char
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
            line += char
        elif char == "{":
            lines.append("  " * level + line.strip() + " {")
            line = ""
            level += 1
        elif char == "}":
            if line.strip():
                lines.append("  " * level + line.strip())
            line = ""
            level -= 1
            lines.append("  " * level + "}")
        elif char == ";":
            lines.append("  " * level + line.strip() + ";")
            line = ""
        elif char in "\n\r\t":
            if line and not line.endswith(" "):
                line += " "
        else:
            line += char
    if line.strip():
        lines.append(line.strip())
    return "\n".join(lines) + "\n"


def generate(root=ROOT):
    root = Path(root)
    linked = link("kernel/omega/main.omega", root, dynamic=True)
    names = set(linked.manifest()["modules"])
    for folder in ("kernel/native", "omega_kernel"):
        names.update(path.relative_to(root).as_posix()
                     for path in (root / folder).rglob("*")
                     if path.suffix in {".c", ".h", ".py"})
    # Reproducible native bootstrap and the exact procedural runtime. These are
    # reused dependencies; the manifest explicitly accounts for their lines.
    names.update("omega_selfhost/" + name for name in (
        "bootstrap.py", "compiler.omega", "runtime.h", "native_std.h", "memory.h", "bounded_rational.h"))
    names.update(path.relative_to(root).as_posix() for path in (root / "testes/kernel").glob("*.*")
                 if path.suffix in {".py", ".c", ".json"})
    names.add("kernel/README.md")
    sources = {name: (root / name).read_text(encoding="utf-8") for name in sorted(names)}
    prefix = ("# Omega kernel: native Omega + explicit C/Python source frames.\n"
              "# Generate: python -m omega_kernel.amalgamation --generate\n"
              "# Foreign sections below are comments, never dynamically evaluated.\n" + _pretty(linked.source))
    hashes = {name: {"sha256": hashlib.sha256(text.encode()).hexdigest(),
                     "bytes": len(text.encode()), "lines": len(text.splitlines()),
                     "trailing_newline": text.endswith("\n")}
              for name, text in sources.items()}
    manifest = {"format": "omega-kernel-amalgamation-1", "files": hashes,
                "prefix_sha256": hashlib.sha256(prefix.encode()).hexdigest(),
                "module_manifest": linked.manifest(),
                "tree_sha256": hashlib.sha256(canonical(hashes)).hexdigest(),
                "line_accounting": {
                    "linked_omega_lines": len(prefix.splitlines()),
                    "new_component_source_lines": sum(info["lines"] for name, info in hashes.items()
                                                      if name.startswith(("kernel/", "omega_kernel/", "testes/kernel/"))),
                    "reused_dependency_source_lines": sum(info["lines"] for name, info in hashes.items()
                                                         if not name.startswith(("kernel/", "omega_kernel/", "testes/kernel/"))),
                    "linked_and_modular_omega_overlap": True,
                    "line_count_is_not_a_correctness_metric": True}}
    pieces = [prefix, HEADER + json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", MARKER]
    for name, text in sources.items():
        pieces.append(FILE + json.dumps(name) + "\n")
        pieces.extend("#|" + line for line in text.splitlines(keepends=True))
        if text and not text.endswith("\n"):
            pieces.append("\n")
        pieces.append(END)
    output = "".join(pieces)
    if len(output.encode()) > MAX_BYTES:
        raise ValueError("Amalgamation byte budget")
    return output


def _safe_name(name):
    if type(name) is not str or len(name) > 512 or ":" in name or "\\" in name:
        raise ValueError("Unsafe embedded source path")
    path = PurePosixPath(name)
    if (str(path) != name or path.is_absolute() or
            any(part in {".", "..", ".git"} for part in path.parts) or not path.parts):
        raise ValueError("Noncanonical embedded source path")
    return path


def inspect(data):
    if type(data) is not bytes or len(data) > MAX_BYTES:
        raise ValueError("Amalgamation input size")
    text = data.decode("utf-8")
    split = text.find("\n" + HEADER)
    if split < 0:
        raise ValueError("Missing amalgamation manifest")
    prefix = text[:split + 1]
    remainder = text[split + 1:]
    header, remainder = remainder.split("\n", 1)
    manifest = decode(header[len(HEADER):].encode(), max_bytes=2*1024**2, max_nodes=100000)
    if (manifest.get("format") != "omega-kernel-amalgamation-1" or
            hashlib.sha256(prefix.encode()).hexdigest() != manifest.get("prefix_sha256") or
            not remainder.startswith(MARKER)):
        raise ValueError("Amalgamation prefix/format integrity")
    expected = manifest.get("files")
    if type(expected) is not dict or len(expected) > 256:
        raise ValueError("Embedded source count budget")
    if hashlib.sha256(canonical(expected)).hexdigest() != manifest.get("tree_sha256"):
        raise ValueError("Amalgamation manifest tree hash")
    sources = {}
    current = None
    lines = []
    for line in remainder[len(MARKER):].splitlines(keepends=True):
        if current is None:
            if not line.startswith(FILE):
                raise ValueError("Unexpected source frame data")
            current = json.loads(line[len(FILE):])
            _safe_name(current)
            if current in sources or current not in expected:
                raise ValueError("Duplicate/unlisted source frame")
            lines = []
        elif line == END:
            source = "".join(lines)
            info = expected[current]
            if source and not info["trailing_newline"]:
                source = source[:-1]
            raw = source.encode()
            if (len(raw) != info["bytes"] or len(source.splitlines()) != info["lines"] or
                    hashlib.sha256(raw).hexdigest() != info["sha256"]):
                raise ValueError("Embedded source hash/size mismatch: " + current)
            sources[current] = raw
            current = None
        else:
            if not line.startswith("#|"):
                raise ValueError("Foreign source escaped its inert comment frame")
            lines.append(line[2:])
    if current is not None or set(sources) != set(expected):
        raise ValueError("Incomplete amalgamation source frames")
    return manifest, sources, prefix.encode()


def extract(data, destination):
    manifest, sources, prefix = inspect(data)
    target = Path(destination).absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError("Extraction destination must not exist")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Build an entire private tree before publishing it. A competing destination
    # must never be overwritten, including an empty directory or a symlink.
    with tempfile.TemporaryDirectory(prefix=".omega-kernel-", dir=target.parent) as tmp:
        stage = Path(tmp) / "tree"
        stage.mkdir()
        for name, raw in sources.items():
            path = stage.joinpath(*_safe_name(name).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(raw)
        (stage / "omega_kernel_linked.omega").write_bytes(prefix)
        # Reuse the existing Linux exclusive atomic publish primitive. It does
        # not load any embedded module; the destination is source data only.
        from omega.omega_3_monolith import _publish
        _publish(stage, target)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--generate", action="store_true")
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--extract", type=Path)
    parser.add_argument("--file", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    if args.generate:
        args.file.write_text(generate(), encoding="utf-8")
    elif args.check:
        if args.file.read_text(encoding="utf-8") != generate():
            raise SystemExit("Stale or modified kernel amalgamation")
    else:
        extract(args.file.read_bytes(), args.extract)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
