"""OM-149: offline wheel reproducibility/installation; pending execution."""
import email
import hashlib
from pathlib import Path
import sys,zipfile
from omega_platform.budget import BUILD_BUDGET
from omega_platform.sandbox import trusted


def test_wheel_reproduces_installs_offline_and_contains_integrated_packages(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[2]
    monkeypatch.setenv('SOURCE_DATE_EPOCH','1700000000')
    monkeypatch.setenv('PYTHONHASHSEED','0')
    wheels=[]
    for name in ('first','second'):
        destination=tmp_path/name
        trusted([sys.executable,'-m','build','--no-isolation','--wheel','--outdir',destination],cwd=root,budget=BUILD_BUDGET,check=True)
        built=list(destination.glob('*.whl'));assert len(built)==1;wheels.append(built[0])
    assert hashlib.sha256(wheels[0].read_bytes()).digest()==hashlib.sha256(wheels[1].read_bytes()).digest()
    with zipfile.ZipFile(wheels[0]) as wheel:
        names=set(wheel.namelist())
        for package in ('omega_agent','omega_coder','omega_memory','omega_learning','omega_tools','omega_security','omega_evolution','omega_bench'):
            assert package+'/__init__.py' in names
        metadata=email.message_from_bytes(wheel.read(next(name for name in names if name.endswith('.dist-info/METADATA'))))
        assert metadata['Name']=='linguagem-omega' and metadata['Version']=='2.0.0'
        assert 'omega_agent/integration.py' in names and 'omega_selfhost/stdlib.omega' in names
    environment=tmp_path/'installed'
    trusted([sys.executable,'-m','venv',environment],budget=BUILD_BUDGET,check=True)
    python=environment/'bin/python'
    trusted([python,'-m','pip','install','--no-index','--no-deps',wheels[0]],budget=BUILD_BUDGET,check=True)
    program="from importlib.metadata import version; from omega_agent.integration import boolean_problem; assert version('linguagem-omega')=='2.0.0'; assert boolean_problem({'id':'p','arity':0,'outputs':[1]}).id=='p'"
    trusted([python,'-I','-c',program],cwd=tmp_path,budget=BUILD_BUDGET,check=True)
