from copy import deepcopy
from fractions import Fraction
import os
from pathlib import Path
import random
import shutil
import tempfile
import unittest

from omega_kernel.amalgamation import OUTPUT, generate, inspect, extract
from omega_kernel.certificates import ProofBuilder, create_tensor_certificate, verify_tensor_certificate
from omega_kernel.protocol import elf_bytes, matrix_values, envelope, decode_execution
from omega_kernel.runtime import request, execute, build
from omega_platform.sandbox import run as isolated_run
from testes.kernel.corpus import examples, arithmetic_cases


class LogicTests(unittest.TestCase):
    def test_proofs_and_independent_omega_checker(self):
        # Snapshot yielded packets immediately: the builder intentionally keeps
        # extending a shared arena and definitions across successive cases.
        for name, packet, accepted in examples():
            with self.subTest(name=name):
                c = request("verify", packet)
                omega = request("verify-omega", packet)
                self.assertEqual(bool(c["accepted"]), accepted, c)
                self.assertEqual(bool(omega["accepted"]), accepted, omega)
                self.assertEqual(bool(c["verified"]), accepted)
                self.assertEqual(c["axioms"], [])

    def test_forward_edges_unknown_fields_and_axioms_rejected(self):
        packet = next(examples())[1]
        variants = []
        altered = deepcopy(packet)
        altered["nodes"][0]["args"] = [999]
        variants.append(altered)
        altered = deepcopy(packet)
        altered["nodes"][0]["axiom"] = "trust-me"
        variants.append(altered)
        altered = deepcopy(packet)
        altered["axioms"] = ["False"]
        variants.append(altered)
        altered = deepcopy(packet)
        altered["definitions"] = [{"type": 0}]
        variants.append(altered)
        for variant in variants:
            with self.subTest(packet=variant):
                result = request("verify", variant)
                self.assertFalse(result["accepted"])
                self.assertFalse(result["verified"])

    def test_resource_exhaustion_is_never_accepted(self):
        packet = deepcopy(next(examples())[1])
        packet["limits"]["fuel"] = 1
        for operation in ("verify", "verify-omega"):
            with self.subTest(operation=operation):
                result = request(operation, packet)
                self.assertFalse(result["accepted"])
                self.assertEqual(result["status"], "resource-limit")

    def test_unchecked_or_recursive_constants_rejected(self):
        b = ProofBuilder()
        nat = b.node("nat")
        constant = b.node("constant", data=(0,))
        packet = b.packet(constant, nat)
        self.assertFalse(request("verify", packet)["accepted"])
        packet["definitions"] = [{"type": nat, "body": constant}]
        self.assertFalse(request("verify", packet)["accepted"])


def matrix(rows, columns, values):
    return {"rows": rows, "columns": columns, "values": values}


class TensorTests(unittest.TestCase):
    def test_batch_simd_scalar_exact_differential(self):
        rng = random.Random(7717)
        a = [[rng.randint(-10000, 10000), rng.randint(1, 127)] for _ in range(71)]
        b = [[rng.randint(-10000, 10000), rng.randint(1, 127)] for _ in range(71)]
        for operation in ("add", "mul"):
            expected = [(Fraction(*x) + Fraction(*y)) if operation == "add"
                        else Fraction(*x) * Fraction(*y) for x, y in zip(a, b)]
            for backend in ("auto", "scalar"):
                with self.subTest(operation=operation, backend=backend):
                    result = request("batch", {"operation": operation, "a": a, "b": b, "backend": backend})
                    self.assertTrue(result["accepted"], result)
                    self.assertEqual([Fraction(n, d) for n, d, error in result["values"]], expected)
                    self.assertTrue(all(error == 0 for n, d, error in result["values"]))
                    self.assertFalse(result["verified"])

    def test_batch_overflow_is_explicit(self):
        packet = {"operation": "mul", "a": [[(1<<63)-1, 1]], "b": [[2, 1]]}
        result = request("batch", packet)
        self.assertFalse(result["accepted"])
        self.assertNotEqual(result["values"][0][2], 0)

    def test_matrix_algorithms_against_native_omega(self):
        a = matrix(2, 3, ["1/3", "-2/7", 5, "4/9", 0, "-1/11"])
        b = matrix(3, 2, ["2/3", 7, 0, "1/6", -1, "3/5"])
        packets = [{"operation": "gemm", "a": a, "b": b}]
        packets += [{"operation": op, "a": a, "b": a} for op in ("add", "sub", "hadamard")]
        packets += [{"operation": op, "a": a} for op in ("transpose", "relu", "sum", "sum-squares")]
        for packet in packets:
            with self.subTest(operation=packet["operation"]):
                c = request("tensor", packet)
                omega = request("tensor-reference", packet)
                self.assertTrue(c["accepted"], c)
                self.assertEqual(matrix_values(c["matrix"]), omega["values"])
                self.assertEqual(int(omega["rows"]), c["matrix"]["rows"])
                self.assertEqual(int(omega["columns"]), c["matrix"]["columns"])

    def test_compact_simd_and_general_gmp_paths(self):
        a = matrix(4, 19, [i % 13 - 6 for i in range(76)])
        b = matrix(19, 3, [i % 11 - 5 for i in range(57)])
        packet = {"operation": "gemm", "a": a, "b": b}
        scalar = request("tensor", dict(packet, backend="scalar"))
        auto = request("tensor", packet)
        self.assertEqual(matrix_values(scalar["matrix"]), matrix_values(auto["matrix"]))
        huge = str(1 << 150)
        packet = {"operation": "gemm", "a": matrix(1, 1, [huge]), "b": matrix(1, 1, [huge]), "bits": 1024}
        result = request("tensor", packet)
        self.assertTrue(result["accepted"], result)
        self.assertEqual(matrix_values(result["matrix"]), [Fraction(1 << 300)])

    def test_shape_denominator_and_bit_limit(self):
        packets = [
            {"operation": "gemm", "a": matrix(1, 2, [1, 2]), "b": matrix(1, 1, [1])},
            {"operation": "sum", "a": matrix(1, 1, ["1/0"])},
            {"operation": "sum", "a": matrix(1, 1, [str(1<<150)]), "bits": 64},
        ]
        for packet in packets:
            with self.subTest(packet=packet):
                self.assertFalse(request("tensor", packet)["accepted"])

    def test_reverse_mode_duplicate_edges_and_relu_zero(self):
        nodes = [
            {"op": "input", "args": [], "matrix": matrix(1, 3, [-2, 0, 3])},
            {"op": "hadamard", "args": [0, 0]},
            {"op": "sum", "args": [1]},
        ]
        result = request("graph", {"nodes": nodes, "output": 2})
        self.assertTrue(result["accepted"], result)
        self.assertEqual(matrix_values(result["values"][2]), [13])
        self.assertEqual(matrix_values(result["gradients"][0]), [-4, 0, 6])
        nodes[1] = {"op": "relu", "args": [0]}
        result = request("graph", {"nodes": nodes, "output": 2})
        self.assertEqual(matrix_values(result["gradients"][0]), [0, 0, 1])

    def test_matmul_reverse_mode(self):
        nodes = [
            {"op": "input", "args": [], "matrix": matrix(1, 2, [2, 3])},
            {"op": "input", "args": [], "matrix": matrix(2, 1, [5, 7])},
            {"op": "matmul", "args": [0, 1]},
            {"op": "sum-squares", "args": [2]},
        ]
        result = request("graph", {"nodes": nodes, "output": 3})
        self.assertTrue(result["accepted"], result)
        self.assertEqual(matrix_values(result["values"][3]), [961])
        self.assertEqual(matrix_values(result["gradients"][0]), [310, 434])
        self.assertEqual(matrix_values(result["gradients"][1]), [124, 186])

    def test_arithmetic_certificate_bound_to_result(self):
        packet = {"operation": "gemm", "a": matrix(1, 2, ["1/3", "2/7"]),
                  "b": matrix(2, 1, [3, 7])}
        result = request("tensor", packet)
        certificate = create_tensor_certificate(packet, result)
        self.assertTrue(verify_tensor_certificate(certificate)["accepted"])
        self.assertTrue(verify_tensor_certificate(certificate, reference=True)["accepted"])
        altered = deepcopy(certificate)
        altered["proof"]["expected"] = altered["proof"]["proof"]
        with self.assertRaises(ValueError):
            verify_tensor_certificate(altered)
        forged = deepcopy(result)
        forged["matrix"]["numerators"][0] = "4"
        forged["matrix"]["denominator"] = "1"
        certificate = create_tensor_certificate(packet, forged)
        self.assertFalse(verify_tensor_certificate(certificate)["accepted"])


class DirectBackendTests(unittest.TestCase):
    def test_all_arithmetic_cases_and_independent_evaluator(self):
        for expression, values, status, expected in arithmetic_cases():
            with self.subTest(expression=expression, inputs=values):
                source = "funcao example(a,b) { retornar " + expression + "; }"
                document = request("compile-source", {"source": source, "architecture": "x86_64"})
                reference = request("evaluate", {"ir": document["ir"], "inputs": values})
                native = execute(document, values)
                self.assertEqual((int(reference["error"]), int(reference["value"])), (status, expected))
                self.assertEqual((native["status"], native["value"]), (status, expected))
                self.assertTrue(native["sandboxed"])

    def test_conditional_lexical_scope(self):
        source = "funcao pick(a,b) { var c=a+b; se(c<0) { var d=-c; retornar d; } senao { var d=c*2; retornar d; } }"
        document = request("compile-source", {"source": source, "architecture": "x86_64"})
        self.assertEqual(execute(document, [-10, 3])["value"], 7)
        self.assertEqual(execute(document, [10, 3])["value"], 26)

    def test_no_parameters_and_int64_min_literal(self):
        source = "funcao smallest() { retornar -9223372036854775808; }"
        document = request("compile-source", {"source": source, "architecture": "x86_64"})
        self.assertEqual(execute(document, [])["value"], -(1<<63))

    def test_short_and_trailing_binary_input_rejected(self):
        document = request("compile-source", {"source": "funcao f(a) { retornar a; }", "architecture": "x86_64"})
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            binary = folder / "program"
            binary.write_bytes(elf_bytes(document))
            binary.chmod(0o500)
            for data in (b"", bytes(7), bytes(9)):
                with self.subTest(bytes=len(data)):
                    path = folder / "arguments"
                    path.write_bytes(data)
                    result = isolated_run([binary, path], readonly=[path])
                    self.assertEqual(decode_execution(result.stdout, result.returncode)["status"], 3)

    def test_cross_architectures(self):
        for arch, variable, executable in (("aarch64", "OMEGA_KERNEL_QEMU_AARCH64", "qemu-aarch64"),
                                            ("riscv64", "OMEGA_KERNEL_QEMU_RISCV64", "qemu-riscv64")):
            with self.subTest(architecture=arch):
                emulator = os.environ.get(variable) or shutil.which(executable)
                if not emulator:
                    self.skipTest("Cross-ISA execution requires " + executable)
                for expression, values, status, expected in arithmetic_cases():
                    document = request("compile-source", {"source": "funcao f(a,b) { retornar " + expression + "; }", "architecture": arch})
                    actual = execute(document, values, emulator=emulator)
                    self.assertEqual((actual["status"], actual["value"]), (status, expected), (arch, expression, values))

    def test_invalid_source_and_effects_rejected(self):
        for source in ("funcao f(a) { retornar missing; }", "funcao f(a) { retornar write(a); }",
                       "funcao f(a) { enquanto(a) { } retornar 0; }",
                       "funcao f(a) { var a=1; retornar a; }", "funcao f(a) { var b=a+1; }"):
            with self.subTest(source=source):
                with self.assertRaises(RuntimeError):
                    request("compile-source", {"source": source, "architecture": "x86_64"})

    def test_elf_permission_and_header_tampering_rejected(self):
        document = request("compile-source", {"source": "funcao f() { retornar 7; }", "architecture": "x86_64"})
        raw = bytearray(elf_bytes(document))
        raw[68] = 7  # RX -> RWX
        altered = dict(document, elf_hex=raw.hex())
        with self.assertRaises(ValueError):
            elf_bytes(altered)
        with self.assertRaises(ValueError):
            decode_execution("00000000000000007\n", 1)


class BundleTests(unittest.TestCase):
    def test_legacy_distribution_delivers_the_new_amalgamation(self):
        import runpy
        from omega_kernel.runtime import ROOT
        legacy = runpy.run_path(str(ROOT / "omega/omega_3_monolith.py"))
        sources = legacy["validated_sources"]()
        self.assertEqual(sources["omega_kernel.omega"], OUTPUT.read_bytes())

    def test_all_sixteen_existing_engines_reachable(self):
        from omega_engines import catalog
        for entry in catalog()["engines"]:
            with self.subTest(engine=entry["id"]):
                result = request("engine", {"id": entry["id"], "data": entry["example"]})
                self.assertIsInstance(result, dict)

    def test_bundle_roundtrip_and_reproducibility(self):
        data = OUTPUT.read_bytes()
        manifest, sources, prefix = inspect(data)
        self.assertEqual(data.decode(), generate())
        self.assertIn("kernel/native/logic.h", sources)
        self.assertIn("funcao principal", prefix.decode())
        self.assertGreaterEqual(len(data.splitlines()), 15000)
        self.assertTrue(manifest["line_accounting"]["linked_and_modular_omega_overlap"])
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sources"
            extract(data, target)
            self.assertEqual((target / "kernel/native/logic.h").read_bytes(), sources["kernel/native/logic.h"])
            with self.assertRaises(FileExistsError):
                extract(data, target)

    def test_modified_prefix_or_source_rejected(self):
        data = OUTPUT.read_bytes()
        for altered in (b"# injected\n" + data, data.replace(b"#|#ifndef OMEGA_EMBEDDED_LOGIC_H", b"#|#ifndef FORGED", 1)):
            with self.subTest(size=len(altered)):
                with self.assertRaises(ValueError):
                    inspect(altered)

    def test_no_float_boolean_or_cyclic_request(self):
        for value in (True, None, 1.25):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    envelope("verify", {"forged": value})
        cyclic = []
        cyclic.append(cyclic)
        with self.assertRaises(ValueError):
            envelope("verify", {"cycle": cyclic})
