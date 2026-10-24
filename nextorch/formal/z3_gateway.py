"""Proof by refutation, with consistency checks and fail-closed solver outcomes."""

import hashlib
import json
from dataclasses import dataclass

import z3


@dataclass(frozen=True)
class VerificationResult:
    status: str
    statement: str
    proof: str = ""
    counterexample: str = ""
    reason: str = ""

    @property
    def valid(self):
        return self.status == "valid"

    @property
    def digest(self):
        return hashlib.sha256(
            json.dumps([self.status, self.statement, self.proof], ensure_ascii=True).encode()
        ).hexdigest()


class FormalVerificationGateway:
    @staticmethod
    def prove(axioms, claim, timeout_ms=2000):
        if timeout_ms <= 0 or not z3.is_bool(claim) or not all(z3.is_bool(a) for a in axioms):
            raise ValueError("Boolean axioms/claim and positive timeout required")
        context = z3.Context(proof=True)
        solver = z3.Solver(ctx=context)
        solver.set(timeout=timeout_ms)
        for axiom in axioms:
            solver.add(axiom.translate(context))
        statement = solver.sexpr() + "\nCLAIM " + claim.sexpr()
        base = solver.check()
        if base == z3.unsat:
            return VerificationResult("inconsistent", statement, reason="Premises are inconsistent")
        if base == z3.unknown:
            return VerificationResult("unknown", statement, reason=solver.reason_unknown())
        solver.add(z3.Not(claim.translate(context)))
        result = solver.check()
        if result == z3.unsat:
            return VerificationResult("valid", statement, proof=solver.proof().sexpr())
        if result == z3.sat:
            return VerificationResult(
                "counterexample", statement, counterexample=str(solver.model())
            )
        return VerificationResult("unknown", statement, reason=solver.reason_unknown())

    @staticmethod
    def certify_deduction(premises, query_src, query_target, timeout_ms=2000):
        indices = [query_src, query_target] + [i for edge in premises for i in edge]
        if any(type(i) is not int or i < 0 for i in indices):
            raise ValueError("Proposition indices must be nonnegative integers")
        context = z3.Context()
        variables = {i: z3.Bool(f"P_{i}", ctx=context) for i in set(indices)}
        axioms = [variables[query_src]]
        axioms.extend(z3.Implies(variables[a], variables[b]) for a, b in premises)
        return FormalVerificationGateway.prove(axioms, variables[query_target], timeout_ms)

    @staticmethod
    def verify_deduction(premises, query_src, query_target):
        return FormalVerificationGateway.certify_deduction(premises, query_src, query_target).valid


Z3Gateway = FormalVerificationGateway
