"""Canonical logical problem encoding and a proof gate for replay admission."""

import asyncio
from dataclasses import dataclass

import torch

from .z3_gateway import FormalVerificationGateway


@dataclass(frozen=True)
class LogicalProblem:
    premises: tuple[tuple[int, int], ...]
    source: int

    def __post_init__(self):
        edges = tuple(tuple(edge) for edge in self.premises)
        if any(len(edge) != 2 for edge in edges):
            raise ValueError("Each premise must have two proposition indices")
        if any(type(i) is not int or i < 0 for i in (self.source, *(i for e in edges for i in e))):
            raise ValueError("Proposition indices must be nonnegative integers")
        object.__setattr__(self, "premises", edges)

    def encode(self, vocab_size, device="cpu"):
        tokens = [self.source] + [i for edge in self.premises for i in edge]
        if max(tokens) >= vocab_size:
            raise ValueError("Problem exceeds model vocabulary")
        return torch.tensor([tokens], dtype=torch.long, device=device)

    def reachable(self):
        visited, frontier = {self.source}, [self.source]
        while frontier:
            current = frontier.pop(0)
            for a, b in self.premises:
                if a == current and b not in visited:
                    visited.add(b)
                    frontier.append(b)
        return sorted(visited)


class FormalBarrier:
    def __init__(self, timeout_ms=2000, require_lean=False, lean_bridge=None):
        self.timeout_ms = timeout_ms
        self.require_lean = require_lean
        self.lean_bridge = lean_bridge

    def _z3(self, problem, target):
        return FormalVerificationGateway.certify_deduction(
            problem.premises, problem.source, target, self.timeout_ms
        )

    async def certify_async(self, problem, target):
        from .lean_bridge import LeanBridge
        from .z3_gateway import VerificationResult

        result = self._z3(problem, target)
        if not result.valid or not self.require_lean:
            return result
        lean = await (self.lean_bridge or LeanBridge()).verify_deduction(problem, target)
        if not lean.valid:
            return VerificationResult("lean_" + lean.status, result.statement, reason=lean.output)
        return VerificationResult(
            "valid", result.statement, proof=result.proof + "\nLEAN KERNEL CHECK\n" + lean.output
        )

    def certify(self, problem, target):
        if not self.require_lean:
            return self._z3(problem, target)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.certify_async(problem, target))
        raise RuntimeError("An event loop is running; await barrier.certify_async instead")
