"""Omega-owned orchestration and atomic admission of Nextorch proposals."""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import tempfile

from omega_open.checker import fingerprint
from .gate import certify, load_verified, validate_domain
from . import lean, native
from .proposer import NeuralBudget, propose

FORMAT = "omega-nextorch-run-1"


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True,
                                    allow_nan=False) + "\n", encoding="utf-8")


def synthesize(tasks, destination, budget=None, require_lean=False, build_native=False):
    if type(tasks) is not list or not 1 <= len(tasks) <= 32:
        raise ValueError("Forneça entre 1 e 32 tarefas")
    for task in tasks:
        validate_domain(task)
    if len({t["id"] for t in tasks}) != len(tasks):
        raise ValueError("IDs duplicados")
    target = Path(destination).resolve()
    if target.exists():
        raise ValueError("O diretório de saída já existe; escolha um novo destino")
    budget = budget or NeuralBudget()
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".omega-admission-", dir=target.parent))
    try:
        records = []
        for index, task in enumerate(tasks):
            proposals, diagnostics = propose(task, budget)
            accepted, decisions = [], []
            for origin, ast in proposals:
                decision = {"origin": origin, "proposal_sha256": fingerprint(ast)}
                try:
                    cert = certify(task, ast, origin)
                except (ValueError, TypeError, RecursionError, OverflowError) as exc:
                    decision.update(accepted=False, reason=str(exc))
                else:
                    accepted.append(cert)
                    decision.update(accepted=True, certificate_sha256=cert["sha256"])
                decisions.append(decision)
            if not accepted:
                raise ValueError("Nenhuma proposta passou pelo núcleo Ômega: " + task["id"])
            selected = min(accepted, key=lambda c: (c["metrics"]["nos"],
                                                   c["metrics"]["profundidade"], c["origin"]))
            stem = f"task_{index:03d}"
            write_json(stage / (stem + ".json"), selected)
            record = {"id": task["id"], "certificate": stem + ".json",
                      "diagnostics": diagnostics, "decisions": decisions,
                      "selected_origin": selected["origin"], "lean": None, "native": None}
            if require_lean:
                record["lean"] = lean.check(selected, stage / (stem + ".lean"))
            if build_native:
                record["native"] = native.build(selected, stage / stem)
            records.append(record)
        manifest = {"format": FORMAT, "budget": asdict(budget), "tasks": records,
                    "nextorch_commit": "d449ab637fc3f89749075714c4d7bd7a2d0bf198"}
        manifest["sha256"] = fingerprint(manifest)
        write_json(stage / "manifest.json", manifest)
        # No active result is published until every required gate succeeds.
        os.rename(stage, target)
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def audit(directory, recheck_lean=False, recheck_native=False):
    directory = Path(directory)
    manifest_path = directory / "manifest.json"
    if manifest_path.stat().st_size > 8_000_000:
        raise ValueError("Manifesto muito grande")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT or manifest.get("sha256") != fingerprint(
            {k: v for k, v in manifest.items() if k != "sha256"}):
        raise ValueError("Manifesto inválido")
    records = manifest["tasks"]
    if type(records) is not list or not 1 <= len(records) <= 32:
        raise ValueError("Lista de tarefas inválida")
    checked = 0
    for i, record in enumerate(records):
        stem = f"task_{i:03d}"
        if record["certificate"] != stem + ".json":
            raise ValueError("Caminho de certificado inválido")
        certificate = load_verified(directory / (stem + ".json"))
        if record["id"] != certificate["task"]["id"] or record["selected_origin"] != certificate["origin"]:
            raise ValueError("Manifesto diverge do certificado")
        if record["lean"] is not None:
            if (directory / (stem + ".lean")).read_text(encoding="utf-8") != lean.source(certificate):
                raise ValueError("Fonte da prova Lean adulterada")
        if recheck_lean:
            lean.check(certificate)
        if record["native"] is not None:
            code = directory / (stem + ".c")
            if code.read_text(encoding="utf-8") != native.source(certificate):
                raise ValueError("Fonte nativa adulterada")
            if native.digest(directory / stem) != record["native"]["binary_sha256"]:
                raise ValueError("Binário nativo adulterado")
            if native.digest(code) != record["native"]["source_sha256"]:
                raise ValueError("Hash da fonte nativa incorreto")
        if recheck_native:
            # Never execute an arbitrary binary supplied by an artifact directory.
            with tempfile.TemporaryDirectory(prefix="omega-reaudit-") as tmp:
                native.build(certificate, Path(tmp) / "circuit")
        checked += certificate["checked_rows"]
    return {"valid": True, "tasks": len(records), "checked_rows": checked,
            "lean_rechecked": recheck_lean, "native_rebuilt": recheck_native}
