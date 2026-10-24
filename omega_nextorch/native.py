"""Native C backend for certified finite Boolean circuits (not tensor IR)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from .gate import verify
from omega_platform.budget import BUILD_BUDGET
from omega_platform.sandbox import c_tool,run as isolated_run


def bytecode(ast):
    op = ast[0]
    if op in ("c", "v"):
        return [[op, ast[1]]]
    return [i for child in ast[1:] for i in bytecode(child)] + [[op]]


def source(certificate):
    if not verify(certificate):
        raise ValueError("O backend nativo exige um certificado válido")
    code = bytecode(certificate["ast"])
    statements = []
    for ins in code:
        op = ins[0]
        if op == "c":
            line = f"s[p++] = {ins[1]};"
        elif op == "v":
            line = f"s[p++] = (row >> {ins[1]}) & 1u;"
        elif op == "not":
            line = "s[p-1] = !s[p-1];"
        elif op == "ite":
            line = "s[p-3] = s[p-3] ? s[p-1] : s[p-2]; p -= 2;"
        else:
            symbol = {"and": "&", "or": "|", "xor": "^"}[op]
            line = f"s[p-2] = s[p-2] {symbol} s[p-1]; --p;"
        statements.append("  " + line)
    rows = certificate["checked_rows"]
    return """/* Generated from a validated Omega Boolean certificate. */
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
static unsigned circuit(unsigned row) {
  (void)row;
""" + f"  unsigned s[{len(code)}], p = 0;\n" + "\n".join(statements) + """
  return s[0];
}
int main(int argc, char **argv) {
  if (argc == 2) {
    char *end = NULL;
    errno = 0;
    unsigned long row = strtoul(argv[1], &end, 10);
""" + f"    if (errno || !argv[1][0] || argv[1][0] == '-' || *end || row >= {rows}u) return 2;\n" + """
    printf("%u\\n", circuit((unsigned)row));
    return 0;
  }
  if (argc != 1) return 2;
  putchar('[');
""" + f"  for (unsigned row = 0; row < {rows}u; ++row) {{\n" + """
    if (row) putchar(',');
    printf("%u", circuit(row));
  }
  puts("]");
  return 0;
}
"""


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(certificate, destination, cc=None):
    """Compile and exhaustively validate before publishing an executable."""
    code = source(certificate)
    compiler = shutil.which(cc or os.environ.get("CC", "cc"))
    if compiler is None:
        raise RuntimeError("Compilador C não encontrado; instale GCC ou Clang")
    target = Path(destination)
    if target.exists() or target.with_suffix(".c").exists():
        raise ValueError("O destino nativo já existe")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".omega-native-", dir=target.parent) as tmp:
        src, exe = Path(tmp) / "circuit.c", Path(tmp) / "circuit"
        src.write_text(code, encoding="utf-8")
        proc = c_tool([compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                        str(src.resolve()), "-o", str(exe.resolve())],inputs=[src],
                        output_directory=Path(tmp),budget=BUILD_BUDGET)
        if proc.returncode:
            raise RuntimeError("Compilação C falhou: " + proc.stderr[-4000:])
        result = isolated_run([str(exe.resolve())])
        if result.returncode or json.loads(result.stdout) != certificate["task"]["outputs"]:
            raise ValueError("Executável diverge da especificação exata")
        metadata = {"backend": "c11-boolean-stack", "compiler": compiler,
                    "checked_rows": certificate["checked_rows"],
                    "source_sha256": digest(src), "binary_sha256": digest(exe)}
        os.replace(src, target.with_suffix(".c"))
        os.replace(exe, target)
    return metadata
