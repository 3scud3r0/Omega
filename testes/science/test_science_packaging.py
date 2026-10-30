"""Source delivery, cache integrity and execution from an offline installed wheel."""
from pathlib import Path
import sys
import zipfile
import os
import pytest
from omega_science.runtime import ROOT,catalog,build
from omega_platform.sandbox import trusted
from omega_platform.budget import BUILD_BUDGET


def test_catalog_covers_exact_requested_files_and_tampered_binary_is_refused():
    entries=catalog()['files']
    assert len(entries)==115
    assert len({e['path'] for e in entries})==115
    assert sum(e['kind']=='native' for e in entries)==97
    assert sum(e['kind']=='formal' for e in entries)==18
    for entry in entries:
        assert (ROOT/entry['path']).is_file()
    binary=build('matematica')
    original=binary.read_bytes()
    try:
        binary.write_bytes(original+b'\x00')
        with pytest.raises(ValueError,match='modified'):build('matematica')
    finally:
        binary.write_bytes(original)
    assert build('matematica')==binary


def test_wheel_contains_all_scientific_sources_and_runs_without_neural_dependencies(tmp_path,monkeypatch):
    wheels=tmp_path/'wheels'
    trusted([sys.executable,'-m','build','--no-isolation','--wheel','--outdir',wheels],cwd=ROOT,budget=BUILD_BUDGET,check=True)
    wheel=next(wheels.glob('*.whl'))
    with zipfile.ZipFile(wheel) as contents:
        names=set(contents.namelist())
        assert 'omega_science/runtime.py' in names and 'omega_science/experiment.py' in names
        for entry in catalog()['files']:
            assert 'omega_native/_sources/'+entry['path'] in names
        assert 'omega_native/_sources/ciencia/catalogo.json' in names
    environment=tmp_path/'isolated-install'
    trusted([sys.executable,'-m','venv',environment],budget=BUILD_BUDGET,check=True)
    python=environment/'bin/python'
    trusted([python,'-m','pip','install','--no-index','--no-deps',wheel],budget=BUILD_BUDGET,check=True)
    # Activation of the already installed sandbox tool is an environment setting,
    # not a fallback that executes scientific code without isolation.
    pinned=ROOT.parent/'.tools/bubblewrap-0.12.0/bin'
    if pinned.is_dir():monkeypatch.setenv('PATH',str(pinned)+os.pathsep+os.environ['PATH'])
    code="from omega_science.runtime import catalog,run; assert len(catalog()['files'])==115; assert run(54,{'n':97})['prime']==1; import importlib.util; assert importlib.util.find_spec('torch') is None"
    trusted([python,'-I','-c',code],cwd=tmp_path,budget=BUILD_BUDGET,check=True)
