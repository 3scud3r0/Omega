"""Regression, adversarial admission, native execution and actual Lean checks."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from omega_open import logic
from omega_open.checker import fingerprint
from omega_nextorch.gate import certify, verify
from omega_nextorch import lean, native, pipeline
from omega_nextorch.proposer import NeuralBudget
from omega_platform.sandbox import run as isolated_run


TASK = {"id": "xor", "arity": 2, "outputs": [0, 1, 1, 0]}
AST = ["xor", ["v", 0], ["v", 1]]
LEAN = os.environ.get("OMEGA_LEAN") or shutil.which("lean")
KERNEL = Path(__file__).resolve().parents[1] / "formal/lean/.lake/build/bin/omega_kernel"


class AdmissionTests(unittest.TestCase):
    def test_all_binary_functions(self):
        for bits in range(16):
            task = {"id": str(bits), "arity": 2, "outputs": [(bits >> i) & 1 for i in range(4)]}
            for _, expr in logic.candidates(task["outputs"], 2):
                self.assertTrue(verify(certify(task, logic.encode(expr), "test")))

    def test_wrong_neural_prediction_rejected(self):
        with self.assertRaisesRegex(ValueError, "contraexemplo"):
            certify(TASK, ["c", 0], "nextorch")

    def test_forged_hash_does_not_authorize_execution(self):
        good = certify(TASK, AST, "nextorch")
        for field, value in (("ast", ["c", 0]), ("checked_rows", 0),
                             ("metrics", {"nos": 1}), ("extra", "surprise")):
            bad = copy.deepcopy(good)
            bad[field] = value
            bad["sha256"] = fingerprint({k: v for k, v in bad.items() if k != "sha256"})
            self.assertFalse(verify(bad), field)

    def test_invalid_unreachable_branch_rejected(self):
        with self.assertRaises(ValueError):
            certify({"id": "zero", "arity": 0, "outputs": [0]},
                    ["ite", ["c", 0], ["c", 0], ["v", 99]], "attack")

    def test_limits_and_boolean_types(self):
        for task in ({**TASK, "arity": 1000000}, {**TASK, "outputs": [False, 1, 1, 0]}):
            with self.assertRaises(ValueError):
                certify(task, AST, "test")
        for value in (0, True, -1, 1001):
            with self.assertRaises(ValueError):
                NeuralBudget(epochs=value)

    def test_constant_domains(self):
        for b in (0, 1):
            self.assertTrue(verify(certify({"id": "const", "arity": 0, "outputs": [b]},
                                           ["c", b], "test")))

    def test_proposal_gate_and_atomic_failure(self):
        proposals = [("wrong-neural", ["c", 0]), ("correct", AST)]
        with tempfile.TemporaryDirectory() as tmp, patch(
                "omega_nextorch.pipeline.propose", return_value=(proposals, {})):
            target = Path(tmp) / "result"
            manifest = pipeline.synthesize([TASK], target)
            self.assertFalse(manifest["tasks"][0]["decisions"][0]["accepted"])
            self.assertEqual(manifest["tasks"][0]["selected_origin"], "correct")
            self.assertTrue(pipeline.audit(target)["valid"])
            with self.assertRaises(ValueError):
                pipeline.synthesize([TASK], target)
            with patch("omega_nextorch.lean.check", side_effect=ValueError("rejected")):
                with self.assertRaises(ValueError):
                    pipeline.synthesize([TASK], Path(tmp) / "failed", require_lean=True)
            self.assertFalse((Path(tmp) / "failed").exists())
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["result"])

    def test_verification_without_neural_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cert.json"
            path.write_text(json.dumps(certify(TASK, AST, "test")))
            code = ("import sys; from omega_nextorch.gate import load_verified; "
                    "load_verified(sys.argv[1]); "
                    "assert 'torch' not in sys.modules; assert 'nextorch' not in sys.modules")
            subprocess.run([sys.executable, "-c", code, str(path)], check=True)


@unittest.skipUnless(shutil.which("cc"), "C compiler unavailable")
class NativeTests(unittest.TestCase):
    def test_native_covers_all_operators_and_rows(self):
        expressions = [AST, ["not", AST], ["and", *AST[1:]], ["or", *AST[1:]],
                       ["ite", ["v", 0], ["c", 1], ["v", 1]], ["c", 1]]
        from omega_open.checker import evaluate
        with tempfile.TemporaryDirectory() as tmp:
            for i, ast in enumerate(expressions):
                task = {**TASK, "outputs": [evaluate(ast, row, 2) for row in range(4)]}
                cert = certify(task, ast, "test")
                target = Path(tmp) / f"native{i}"
                metadata = native.build(cert, target)
                self.assertEqual(metadata["checked_rows"], 4)
                for row in range(4):
                    value = isolated_run([target,str(row)],check=True).stdout
                    self.assertEqual(int(value), task["outputs"][row])
                for invalid in ("-1", "4", "junk", ""):
                    self.assertNotEqual(isolated_run([target,invalid]).returncode, 0)
            with self.assertRaises(ValueError):
                native.build(cert, target)

    def test_corrupt_native_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
                "omega_nextorch.pipeline.propose", return_value=([("test", AST)], {})):
            target = Path(tmp) / "result"
            pipeline.synthesize([TASK], target, build_native=True)
            self.assertTrue(pipeline.audit(target, recheck_native=True)["valid"])
            (target / "task_000").write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError, "Binário"):
                pipeline.audit(target)


@unittest.skipUnless(LEAN, "Lean 4 unavailable")
class LeanTests(unittest.TestCase):
    def test_kernel_and_task_proof(self):
        certificate = certify(TASK, AST, "test")
        result = lean.check(certificate, executable=LEAN)
        self.assertTrue(result["valid"])
        self.assertNotIn("sorryAx", result["output"])

    def test_lean_rejects_false_table_even_if_python_is_bypassed(self):
        text = lean.source(certify(TASK, AST, "test"))
        text = text.replace("def circuit : Expr := .xor (.var 0) (.var 1)",
                            "def circuit : Expr := .lit false")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Bad.lean"
            path.write_text(text)
            result = subprocess.run([LEAN, str(path)], capture_output=True, text=True, timeout=60)
            self.assertNotEqual(result.returncode, 0)

    def test_lean_unavailable_fails_closed(self):
        with self.assertRaises(RuntimeError):
            lean.check(certify(TASK, AST, "test"), executable="/nonexistent/lean")


class NeuralIntegrationTests(unittest.TestCase):
    def test_real_nextorch_proposals_are_independently_admitted(self):
        try:
            import torch
        except ImportError:
            self.skipTest("Install the neural extra")
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "actual"
            manifest = pipeline.synthesize([TASK], target,
                NeuralBudget(epochs=3, width=8, candidates=2, policy_steps=1))
            row = manifest["tasks"][0]
            self.assertEqual(row["diagnostics"]["epochs"], 3)
            self.assertGreater(row["diagnostics"]["mean_active_sae_features"], 0)
            self.assertEqual(len(row["decisions"]), 2)
            self.assertTrue(pipeline.audit(target)["valid"])


@unittest.skipUnless(KERNEL.is_file(), "Build the native Lean kernel with lake build")
class StandaloneKernelTests(unittest.TestCase):
    def test_native_lean_kernel_compiles_and_rejects_forgery(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cert.json"
            certificate = certify(TASK, AST, "test")
            path.write_text(json.dumps(certificate))
            result = subprocess.run([str(KERNEL), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["instructions"], native.bytecode(AST))
            certificate["ast"] = ["c", 0]
            path.write_text(json.dumps(certificate))
            result = subprocess.run([str(KERNEL), str(path)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
