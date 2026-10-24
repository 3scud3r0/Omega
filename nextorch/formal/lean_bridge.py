"""Asynchronous Lean 4 checking of a restricted propositional proof language.

Only generated Bool/Prop deduction statements and a small, kernel-checked tactic
subset are admitted. Arbitrary Lean metaprograms are not safe to execute; this
API deliberately does not run user-supplied Lean files/imports or a permissive REPL.
Every check uses a fresh process, a hard timeout and checks #print axioms.
"""

import asyncio
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .barrier import LogicalProblem


@dataclass(frozen=True)
class LeanResult:
    status: str
    output: str = ""

    @property
    def valid(self):
        return self.status == "valid"


class LeanBridge:
    def __init__(self, executable=None, timeout=10.0):
        self.executable = executable or os.environ.get("NEXTORCH_LEAN") or shutil.which("lean")
        self.timeout = timeout
        if timeout <= 0:
            raise ValueError("Lean timeout must be positive")

    @staticmethod
    def _source(problem: LogicalProblem, target: int, proof: str):
        if type(target) is not int or target < 0:
            raise ValueError("Invalid proposition index")
        # Restriction is an allowlist of proof tokens, not a blacklist for arbitrary Lean.
        tokens = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|[()·;,.]|\s+", proof)
        if "".join(tokens) != proof:
            raise ValueError("Proof contains syntax outside the supported tactic subset")
        identifiers = re.findall(r"[A-Za-z_][A-Za-z_0-9]*", proof)
        allowed = {
            "by",
            "exact",
            "apply",
            "assumption",
            "intro",
            "intros",
            "constructor",
            "first",
            "rfl",
            "hp",
        } | {f"h{i}" for i in range(len(problem.premises))}
        if not identifiers or identifiers[0] != "by" or any(i not in allowed for i in identifiers):
            raise ValueError(
                "Unsupported tactic/identifier; axioms, sorry and metaprograms are forbidden"
            )
        props = sorted({problem.source, target, *(i for e in problem.premises for i in e)})
        binders = " ".join(f"(P{i} : Prop)" for i in props)
        hypotheses = " ".join(f"(h{i} : P{a} → P{b})" for i, (a, b) in enumerate(problem.premises))
        return (
            f"set_option maxHeartbeats 100000\n"
            f"theorem nextorch_checked {binders} {hypotheses} (hp : P{problem.source}) "
            f": P{target} := {proof}\n#print axioms nextorch_checked\n"
        )

    async def verify(self, problem, target, proof):
        try:
            source = self._source(problem, target, proof)
        except ValueError as exc:
            return LeanResult("rejected", str(exc))
        if not self.executable:
            return LeanResult("unavailable", "Lean 4 executable not found; configure NEXTORCH_LEAN")
        with tempfile.TemporaryDirectory(prefix="nextorch-lean-") as directory:
            path = Path(directory) / "Proof.lean"
            path.write_text(source, encoding="utf-8")
            try:
                process = await asyncio.create_subprocess_exec(
                    self.executable,
                    str(path),
                    cwd=directory,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
            except OSError as exc:
                return LeanResult("unavailable", str(exc))
            try:
                output, _ = await asyncio.wait_for(process.communicate(), self.timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
                process.kill()
                await process.wait()
                if isinstance(exc, asyncio.CancelledError):
                    raise
                return LeanResult("timeout", "Lean check exceeded its time budget")
            text = output.decode("utf-8", errors="replace")
            clean = "does not depend on any axioms" in text
            # Unused-premise warnings are benign; kernel errors and extra axioms still reject.
            if process.returncode == 0 and clean:
                return LeanResult("valid", text)
            return LeanResult("invalid", text)

    async def verify_deduction(self, problem, target):
        # Construct a proof term by explicit implication application along a BFS path.
        terms, queue = {problem.source: "hp"}, [problem.source]
        while queue:
            src = queue.pop(0)
            for i, (a, b) in enumerate(problem.premises):
                if a == src and b not in terms:
                    terms[b] = f"(h{i} {terms[a]})"
                    queue.append(b)
        if target not in terms:
            return LeanResult("invalid", "No implication path from source to target")
        return await self.verify(problem, target, "by exact " + terms[target])
