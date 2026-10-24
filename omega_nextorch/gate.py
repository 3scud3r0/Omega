"""Independent admission of finite Boolean circuits. No neural imports."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from omega_open.checker import canonical, evaluate, fingerprint, validate_task, validate_tree

FORMAT = "omega-nextorch-certificate-1"
MAX_ROWS = 4096
MAX_NODES = 20000
MAX_DEPTH = 128


def validate_domain(task):
    # Check the bound before validate_task computes 2**arity.
    if type(task) is not dict or type(task.get("arity")) is not int:
        raise ValueError("Tarefa inválida")
    if not 0 <= task["arity"] <= 12:
        raise ValueError("A certificação aceita Bool^0 até Bool^12 (4096 linhas)")
    validate_task(task, MAX_ROWS)


def circuit_metrics(ast, arity):
    validate_tree(ast, arity, MAX_NODES)
    stack = [(ast, 1)]
    unique = set()
    depth = 0
    while stack:
        node, level = stack.pop()
        if level > MAX_DEPTH:
            raise ValueError("Circuito excede a profundidade máxima")
        depth = max(depth, level)
        unique.add(canonical(node))
        if node[0] not in ("c", "v"):
            stack.extend((child, level + 1) for child in node[1:])
    return {"nos": len(unique), "profundidade": depth,
            "operacoes": sum(json.loads(n)[0] not in ("c", "v") for n in unique)}


def certify(task, ast, origin):
    """Reject malformed or incorrect proposals, including unreachable branches."""
    validate_domain(task)
    if type(origin) is not str or not origin:
        raise ValueError("Origem deve ser uma string não vazia")
    metrics = circuit_metrics(ast, task["arity"])
    for row, expected in enumerate(task["outputs"]):
        if evaluate(ast, row, task["arity"]) != expected:
            raise ValueError(f"Proposta rejeitada: contraexemplo na linha {row}")
    body = {"format": FORMAT, "task": copy.deepcopy(task), "ast": copy.deepcopy(ast),
            "origin": origin, "metrics": metrics, "checked_rows": len(task["outputs"])}
    return {**body, "sha256": fingerprint(body)}


def verify(certificate):
    """Recompute admission; a hash alone never authorizes execution."""
    try:
        expected = certify(certificate["task"], certificate["ast"], certificate["origin"])
        return canonical(certificate) == canonical(expected)
    except (KeyError, ValueError, TypeError, RecursionError, OverflowError, IndexError):
        return False


def load_verified(path):
    path = Path(path)
    if path.stat().st_size > 8_000_000:
        raise ValueError("Certificado excede o limite de 8 MB")
    certificate = json.loads(path.read_text(encoding="utf-8"))
    if not verify(certificate):
        raise ValueError("Certificado Ômega/Nextorch inválido")
    return certificate
