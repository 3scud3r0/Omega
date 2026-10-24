import asyncio
import os
import shutil

import pytest
import z3

from nextorch.formal import FormalVerificationGateway as Gateway
from nextorch.formal import LeanBridge, LogicalProblem


def test_z3_proves_transitivity_emits_proof_and_rejects_converse():
    result = Gateway.certify_deduction([(0, 1), (1, 2)], 0, 2)
    assert result.valid and result.proof and len(result.digest) == 64
    invalid = Gateway.certify_deduction([(0, 1), (1, 2)], 2, 0)
    assert invalid.status == "counterexample" and invalid.counterexample
    assert not Gateway.verify_deduction([(0, 1)], 0, 99)
    assert Gateway.verify_deduction([(100, 200)], 100, 200)


def test_z3_handles_general_arithmetic_and_inconsistent_axioms():
    x = z3.Int("x")
    assert Gateway.prove([x > 2], x > 0).valid
    bad = Gateway.prove([x > 0, x < 0], x == 999)
    assert bad.status == "inconsistent" and not bad.valid
    with pytest.raises(ValueError):
        Gateway.prove([], z3.Bool("p"), timeout_ms=0)


def test_unknown_is_fail_closed(monkeypatch):
    class Solver:
        def set(self, **kwargs):
            pass

        def add(self, *args):
            pass

        def sexpr(self):
            return ""

        def check(self):
            return z3.unknown

        def reason_unknown(self):
            return "timeout"

    monkeypatch.setattr(z3, "Solver", lambda **kwargs: Solver())
    result = Gateway.prove([], z3.Bool("p"))
    assert result.status == "unknown" and not result.valid and result.reason == "timeout"


def test_problem_encoding_is_untruncated_and_keeps_edge_directions():
    problem = LogicalProblem(((3, 1), (1, 5), (5, 2), (2, 7), (7, 8)), 3)
    assert problem.encode(10).tolist() == [[3, 3, 1, 1, 5, 5, 2, 2, 7, 7, 8]]
    assert problem.reachable() == [1, 2, 3, 5, 7, 8]
    with pytest.raises(ValueError):
        problem.encode(8)
    with pytest.raises(ValueError):
        LogicalProblem(((0, -1),), 0)


@pytest.mark.parametrize(
    "proof",
    [
        "by sorry",
        "by exact sorryAx",
        "by native_decide",
        "by run_tac evil",
        "by exact hp\naxiom evil : False",
        "by exact hp -- sorry",
    ],
)
def test_lean_rejects_axioms_and_code_before_spawning(proof):
    result = asyncio.run(
        LeanBridge(executable="/not-used").verify(LogicalProblem(((0, 1),), 0), 1, proof)
    )
    assert result.status == "rejected"


def test_missing_lean_is_explicit_not_a_certificate():
    bridge = LeanBridge(executable="/does/not/exist")
    result = asyncio.run(bridge.verify_deduction(LogicalProblem(((0, 1),), 0), 1))
    assert result.status == "unavailable" and not result.valid


@pytest.mark.lean
@pytest.mark.skipif(
    not (os.environ.get("NEXTORCH_LEAN") or shutil.which("lean")), reason="Lean 4 unavailable"
)
def test_real_lean_valid_invalid_and_unreachable():
    bridge = LeanBridge()
    problem = LogicalProblem(((0, 1), (1, 2)), 0)
    result = asyncio.run(bridge.verify_deduction(problem, 2))
    assert result.valid, result.output
    assert "does not depend on any axioms" in result.output
    bad = asyncio.run(bridge.verify(problem, 2, "by exact hp"))
    assert not bad.valid and bad.status == "invalid"
    unreachable = asyncio.run(bridge.verify_deduction(problem, 9))
    assert unreachable.status == "invalid"


def test_z3_matches_graph_reachability_on_random_implication_systems():
    import random

    rng = random.Random(4)
    for _ in range(15):
        edges = tuple((rng.randrange(6), rng.randrange(6)) for _ in range(8))
        problem = LogicalProblem(edges, rng.randrange(6))
        reachable = problem.reachable()
        for target in range(6):
            assert Gateway.verify_deduction(edges, problem.source, target) == (target in reachable)


def test_dual_barrier_rejects_unavailable_lean_even_after_z3_acceptance():
    from nextorch.evolution import CertifiedReplayBuffer
    from nextorch.formal import FormalBarrier

    barrier = FormalBarrier(require_lean=True, lean_bridge=LeanBridge(executable="/not/installed"))
    replay = CertifiedReplayBuffer(barrier=barrier)
    added, result = replay.admit(LogicalProblem(((0, 1),), 0), 1)
    assert not added and result.status == "lean_unavailable" and len(replay) == 0


@pytest.mark.lean
@pytest.mark.skipif(
    not (os.environ.get("NEXTORCH_LEAN") or shutil.which("lean")), reason="Lean 4 unavailable"
)
def test_dual_barrier_requires_both_proofs_and_preserves_policy_on_reload(tmp_path):
    from nextorch.evolution import CertifiedReplayBuffer
    from nextorch.formal import FormalBarrier

    replay = CertifiedReplayBuffer(barrier=FormalBarrier(require_lean=True))
    problem = LogicalProblem(((0, 1), (1, 2)), 0)
    assert replay.admit(problem, 2)[0]
    certificate = next(iter(replay)).certificate
    assert (
        "LEAN KERNEL CHECK" in certificate.proof
        and "does not depend on any axioms" in certificate.proof
    )
    assert not replay.admit(problem, 3)[0]
    replay.save(tmp_path / "dual.json")
    restored = CertifiedReplayBuffer.load(tmp_path / "dual.json")
    assert restored.barrier.require_lean and len(restored) == 1
    assert asyncio.run(restored.barrier.certify_async(problem, 2)).valid


@pytest.mark.lean
@pytest.mark.skipif(
    not (os.environ.get("NEXTORCH_LEAN") or shutil.which("lean")), reason="Lean 4 unavailable"
)
def test_dual_engine_accepts_valid_proofs_with_unused_hypotheses(tmp_path):
    import torch

    from nextorch import NextorchConfig, NextorchEngine

    torch.manual_seed(0)
    config = NextorchConfig(
        vocab_size=4, d_model=8, n_features=32, thought_steps=1, require_lean=True
    )
    engine = NextorchEngine(config=config)
    problem = LogicalProblem(((0, 1), (1, 2)), 0)
    # Both hp (reflexivity) and h0 hp leave some binders unused.
    assert engine.barrier.certify(problem, 0).valid
    assert engine.barrier.certify(problem, 1).valid
    report = engine.execute_self_improvement_cycle(problems=[problem])
    assert report.replay_size >= 1 and report.loss is not None
    assert all("LEAN KERNEL CHECK" in entry.certificate.proof for entry in engine.replay)
    path = tmp_path / "dual.pt"
    engine.save_checkpoint(path)
    restored = NextorchEngine.load_checkpoint(path)
    assert restored.config.require_lean and restored.replay.barrier.require_lean
    assert len(restored.replay) == len(engine.replay)
