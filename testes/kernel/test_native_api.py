from pathlib import Path
import shutil
import tempfile
import unittest

from omega_platform.budget import BUILD_BUDGET, COMPILER_BUDGET
from omega_platform.sandbox import c_tool, instrumented, run
from omega_kernel.runtime import ROOT, request


class NativeAPITests(unittest.TestCase):
    def test_freestanding_header_compilation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "freestanding.c"
            source.write_text('#include "logic.h"\n'
                              'int check(ok_checker *s, unsigned p, unsigned t) { return ok_verify(s,p,t); }\n')
            c_tool([shutil.which("cc"), "-std=c11", "-ffreestanding", "-fno-builtin", "-O2",
                    "-I", ROOT / "kernel/native", "-c", source, "-o", folder / "proof.o"],
                   inputs=[ROOT / "kernel/native", ROOT / "omega_selfhost", source],
                   output_directory=folder, budget=BUILD_BUDGET, check=True)
            self.assertGreater((folder / "proof.o").stat().st_size, 0)

    def test_adversarial_c_api_under_asan_ubsan(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = ROOT / "testes/kernel/native_checks.c"
            binary = folder / "checks"
            c_tool([shutil.which("cc"), "-std=c11", "-O1", "-g", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", source, "-o", binary],
                   inputs=[ROOT / "testes/kernel", ROOT / "kernel/native", ROOT / "omega_selfhost"],
                   output_directory=folder, budget=BUILD_BUDGET, check=True)
            result = instrumented([binary], budget=COMPILER_BUDGET, check=True)
            self.assertEqual(result.stdout.strip(), "native-kernel-api-checks: passed")

    def test_gmp_graph_adapter_under_asan_ubsan(self):
        nodes = [{"op": "input", "args": [], "matrix": {"rows": 1, "columns": 2, "values": ["1/3", -2]}},
                 {"op": "hadamard", "args": [0, 0]}, {"op": "sum", "args": [1]}]
        self.assertTrue(request("graph", {"nodes": nodes, "output": 2}, diagnostic=True)["accepted"])
