"""Additional Omega commands, imported without importing PyTorch."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess


COMMANDS = ("intuition", "audit-intuition", "verify-intuition", "compile-native", "prove-lean")


def register(subparsers):
    p = subparsers.add_parser("intuition", help="Nextorch propõe; Ômega certifica circuitos booleanos")
    p.add_argument("arquivo", type=Path)
    p.add_argument("--saida", type=Path, required=True)
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--width", type=int, default=16)
    p.add_argument("--candidates", type=int, default=4)
    p.add_argument("--policy-steps", type=int, default=3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--lean", action="store_true")
    p.add_argument("--native", action="store_true")
    p = subparsers.add_parser("audit-intuition", help="revalida independentemente uma execução")
    p.add_argument("arquivo", type=Path)
    p.add_argument("--lean", action="store_true")
    p.add_argument("--native", action="store_true")
    for command in ("verify-intuition", "compile-native", "prove-lean"):
        p = subparsers.add_parser(command)
        p.add_argument("arquivo", type=Path)
        if command != "verify-intuition":
            p.add_argument("--saida", type=Path, required=True)


def execute(args):
    from .gate import load_verified
    from .pipeline import audit, synthesize
    from .proposer import NeuralBudget
    from . import lean, native

    try:
        if args.acao == "intuition":
            if args.arquivo.stat().st_size > 8_000_000:
                raise ValueError("Arquivo de tarefas excede 8 MB")
            doc = json.loads(args.arquivo.read_text(encoding="utf-8"))
            tasks = doc["tasks"] if "tasks" in doc else [doc]
            result = synthesize(tasks, args.saida,
                                NeuralBudget(args.epochs, args.width, args.candidates,
                                             args.policy_steps, args.seed), args.lean, args.native)
            result = {"valid": True, "tasks": len(result["tasks"]), "output": str(args.saida),
                      "lean": args.lean, "native": args.native}
        elif args.acao == "audit-intuition":
            result = audit(args.arquivo, args.lean, args.native)
        else:
            certificate = load_verified(args.arquivo)
            if args.acao == "compile-native":
                result = native.build(certificate, args.saida)
            elif args.acao == "prove-lean":
                if args.saida.exists():
                    raise ValueError("O destino da prova já existe")
                result = lean.check(certificate, args.saida)
            else:
                result = {"valid": True, "checked_rows": certificate["checked_rows"]}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (RuntimeError, subprocess.SubprocessError) as exc:
        raise ValueError(str(exc)) from exc
