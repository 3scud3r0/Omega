"""Installed native engines need neither a checkout nor neural Python packages."""
from pathlib import Path
import os
import sys
import zipfile

from omega_engines import catalog
from omega_science.runtime import ROOT
from omega_platform.budget import BUILD_BUDGET
from omega_platform.sandbox import trusted


def test_wheel_delivers_sixteen_engines_lean_and_c_backend_and_runs_offline(tmp_path,monkeypatch):
    wheels=tmp_path/'wheels'
    trusted([sys.executable,'-m','build','--no-isolation','--wheel','--outdir',wheels],cwd=ROOT,budget=BUILD_BUDGET,check=True)
    wheel=next(wheels.glob('*.whl'))
    with zipfile.ZipFile(wheel) as archive:
        names=set(archive.namelist())
        assert 'omega_engines/cli.py' in names and 'omega_engines/proof.py' in names
        for entry in catalog()['engines']:assert 'omega_native/_sources/'+entry['path'] in names
        for path in ('omega_core/catalogo.json','omega_core/algebra.omega','omega_core/formal/HamiltonPrinciple.lean','runtime/cellular_micro_arena.h'):
            assert 'omega_native/_sources/'+path in names
    environment=tmp_path/'installed'
    trusted([sys.executable,'-m','venv',environment],budget=BUILD_BUDGET,check=True)
    python=environment/'bin/python'
    trusted([python,'-m','pip','install','--no-index','--no-deps',wheel],budget=BUILD_BUDGET,check=True)
    pinned=ROOT.parent/'.tools/bubblewrap-0.12.0/bin'
    if pinned.is_dir():monkeypatch.setenv('PATH',str(pinned)+os.pathsep+os.environ['PATH'])
    code="from omega_engines import catalog,run; c=catalog(); assert len(c['engines'])==16; assert run(3,c['engines'][2]['example'])['objective']==10; import importlib.util; assert importlib.util.find_spec('torch') is None"
    trusted([python,'-I','-c',code],cwd=tmp_path,budget=BUILD_BUDGET,check=True)
