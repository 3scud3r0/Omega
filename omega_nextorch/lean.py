"""Render only validated circuits into closed, reproducible Lean proof sources."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
from dataclasses import replace
from omega_platform.budget import PROOF_BUDGET
from omega_platform.sandbox import trusted
import tempfile

from .gate import verify
from .native import bytecode


def expression(ast):
    op = ast[0]
    if op == "c":
        return ".lit " + ("true" if ast[1] else "false")
    if op == "v":
        return f".var {ast[1]}"
    name = {"not": "neg", "and": "conj", "or": "disj", "xor": "xor", "ite": "ite"}[op]
    return "." + name + " " + " ".join("(" + expression(a) + ")" for a in ast[1:])


def source(certificate):
    if not verify(certificate):
        raise ValueError("Lean exige um certificado Ômega válido")
    kernel = Path(__file__).with_name("Kernel.lean").read_text(encoding="utf-8")
    rows = [f"((fun j => ({i} / 2^j) % 2 == 1), {'true' if b else 'false'})"
            for i, b in enumerate(certificate["task"]["outputs"])]
    instructions = []
    for ins in bytecode(certificate["ast"]):
        if ins[0] == "c":
            instructions.append(".push " + ("true" if ins[1] else "false"))
        elif ins[0] == "v":
            instructions.append(f".load {ins[1]}")
        else:
            instructions.append("." + {"not": "neg", "and": "conj", "or": "disj",
                                       "xor": "xor", "ite": "ite"}[ins[0]])
    return kernel + "\nset_option maxRecDepth 100000\nset_option maxHeartbeats 4000000\nnamespace OmegaCertificate\nopen Omega\n" + \
        "def circuit : Expr := " + expression(certificate["ast"]) + "\n" + \
        "def rows : List ((Nat → Bool) × Bool) := [" + ",\n".join(rows) + "]\n" + \
        "def instructions : List Instr := [" + ", ".join(instructions) + "]\n" + """
theorem table_checked : check circuit rows = true := by decide
theorem lowering_matches : instructions = compile circuit := by rfl
theorem accepted_execution (row) (hm : row ∈ rows) (s : List Bool) :
    run row.1 instructions s = some (row.2 :: s) := by
  rw [lowering_matches]
  exact certified_execution circuit rows table_checked row hm s
#print axioms table_checked
#print axioms lowering_matches
#print axioms accepted_execution
end OmegaCertificate
"""


def check(certificate, destination=None, executable=None, timeout=60):
    generated = source(certificate)
    lean = shutil.which(executable or os.environ.get("OMEGA_LEAN", "lean"))
    if lean is None:
        raise RuntimeError("Lean 4 ausente; configure OMEGA_LEAN com o executável")
    with tempfile.TemporaryDirectory(prefix="omega-lean-") as tmp:
        proof = Path(tmp) / "Certificate.lean"
        proof.write_text(generated, encoding="utf-8")
        proc = trusted([lean, str(proof)], budget=replace(PROOF_BUDGET,wall_seconds=timeout))
        output = proc.stdout + proc.stderr
        if proc.returncode or "sorryAx" in output or "warning:" in output:
            raise ValueError("Lean rejeitou a prova: " + output[-4000:])
        # These declarations must have been elaborated, not just a successful process.
        for declaration in ("Omega.compile_correct", "Omega.check_sound",
                            "OmegaCertificate.table_checked", "OmegaCertificate.accepted_execution"):
            if "'" + declaration + "'" not in output:
                raise ValueError("Saída Lean incompleta: " + declaration)
    if destination is not None:
        Path(destination).write_text(generated, encoding="utf-8")
    return {"valid": True, "scope": "finite-boolean-kernel-and-stack-compiler",
            "axioms": ["propext", "Quot.sound"], "output": output}
