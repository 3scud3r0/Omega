"""Small reproducible CLI demonstrating actual synthesis, proof checking and learning."""

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import torch

from .config import NextorchConfig, seed_everything
from .core import ManifoldAnalyzer
from .engine import ContinuousReasoner
from .evolution import NextorchEngine
from .evolution.replay_buffer import atomic_json
from .formal import LeanBridge, LogicalProblem
from .synthesis import GFlowNetSynthesizer
from .verifier import ZeroCostVerifier


def main(argv=None):
    parser = argparse.ArgumentParser(prog="nextorch")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Run synthesis and proof-gated expert iteration on CPU")
    demo.add_argument("--cycles", type=int, default=2)
    demo.add_argument("--problems", type=int, default=8)
    demo.add_argument("--width", type=int, default=32)
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--output", type=Path, default=Path("artifacts/demo"))
    demo.add_argument(
        "--lean", action="store_true", help="Also require a real Lean deduction check"
    )
    verify = sub.add_parser("verify", help="Verify a JSON implication problem using Z3")
    verify.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    if args.command == "verify":
        from .formal import FormalVerificationGateway

        payload = json.loads(args.file.read_text())
        problem = LogicalProblem(tuple(tuple(e) for e in payload["premises"]), payload["source"])
        result = FormalVerificationGateway.certify_deduction(
            problem.premises, problem.source, payload["target"]
        )
        print(json.dumps(asdict(result), indent=2))
        return 0 if result.valid else 1
    if min(args.cycles, args.problems, args.width) <= 0:
        parser.error("cycles, problems and width must be positive")
    torch.set_num_threads(min(torch.get_num_threads(), 4))
    seed_everything(args.seed)
    config = NextorchConfig(d_model=args.width, n_features=4 * args.width, seed=args.seed)
    engine = NextorchEngine(config=config)
    inputs = torch.randn(128, 6) @ torch.randn(6, 12)
    signature = ManifoldAnalyzer.compute_spectral_signature(inputs)
    flow = GFlowNetSynthesizer(width=args.width, max_depth=3)
    optimizer = torch.optim.Adam(flow.parameters(), lr=0.01)
    policy_training = [flow.train_step(signature, 2, optimizer) for _ in range(3)]
    synthesized = flow.synthesize(signature, 2, candidates=4)
    diagnostics = ZeroCostVerifier.evaluate(ContinuousReasoner(engine.reasoner), (2, args.width))
    reports = []
    for _ in range(args.cycles):
        report = asdict(engine.execute_self_improvement_cycle(n_problems=args.problems))
        reports.append(report)
        print(json.dumps(report))
    lean_result = None
    if args.lean:
        lean_result = asyncio.run(
            LeanBridge().verify_deduction(LogicalProblem(((0, 1), (1, 2)), 0), 2)
        )
        if not lean_result.valid:
            print(json.dumps(asdict(lean_result)))
            return 1
    args.output.mkdir(parents=True, exist_ok=True)
    engine.save_checkpoint(args.output / "checkpoint.pt")
    engine.replay.save(args.output / "certified_replay.json")
    summary = {
        "seed": args.seed,
        "intrinsic_dim": signature["intrinsic_dim"],
        "architecture": synthesized.architecture.to_dict(),
        "synthesis_diagnostics": synthesized.diagnostics,
        "gflownet_training": policy_training,
        "reasoner_diagnostics": diagnostics,
        "cycles": reports,
        "lean": asdict(lean_result) if lean_result else None,
    }
    atomic_json(args.output / "report.json", summary)
    print(f"Saved report, certified replay and checkpoint to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
