"""Offline installed-wheel smoke test for all three kernel components."""
import os
from pathlib import Path
import sys
import zipfile

from omega_kernel.runtime import ROOT
from omega_platform.budget import BUILD_BUDGET
from omega_platform.sandbox import trusted


def test_installed_wheel_includes_bundle_and_runs_proof_tensor_and_elf(tmp_path, monkeypatch):
    wheels = tmp_path / "wheels"
    trusted([sys.executable, "-m", "build", "--no-isolation", "--wheel", "--outdir", wheels],
            cwd=ROOT, budget=BUILD_BUDGET, check=True)
    wheel = next(wheels.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        for name in ("omega_kernel/omega_kernel.omega", "omega_kernel/runtime.py",
                     "omega_native/_sources/kernel/native/main.c",
                     "omega_native/_sources/kernel/native/logic.h",
                     "omega_native/_sources/kernel/omega/main.omega",
                     "omega_native/_sources/omega_selfhost/bounded_rational.h"):
            assert name in names
    environment = tmp_path / "installed"
    trusted([sys.executable, "-m", "venv", environment], budget=BUILD_BUDGET, check=True)
    python = environment / "bin/python"
    trusted([python, "-m", "pip", "install", "--no-index", "--no-deps", wheel],
            budget=BUILD_BUDGET, check=True)
    pinned = ROOT.parent / ".tools/bubblewrap-0.12.0/bin"
    if pinned.is_dir():
        monkeypatch.setenv("PATH", str(pinned) + os.pathsep + os.environ["PATH"])
    code = '''
from omega_kernel.runtime import request,execute
from omega_kernel.certificates import ProofBuilder
from omega_kernel.amalgamation import OUTPUT,inspect
from omega_kernel.protocol import matrix_values
import importlib.util
b=ProofBuilder(); n=b.node('nat'); v=b.node('nat-literal',data=(7,))
assert request('verify',b.packet(v,n))['accepted']
t=request('tensor',{'operation':'sum','a':{'rows':1,'columns':2,'values':['1/3','2/3']}})
assert t['accepted'] and matrix_values(t['matrix'])==[1]
c=request('compile-source',{'source':'funcao f(a,b) { retornar a*b; }','architecture':'x86_64'})
assert execute(c,[6,7])['value']==42
assert inspect(OUTPUT.read_bytes())[0]['format']=='omega-kernel-amalgamation-1'
assert importlib.util.find_spec('torch') is None
'''
    trusted([python, "-I", "-c", code], cwd=tmp_path, budget=BUILD_BUDGET, check=True)
