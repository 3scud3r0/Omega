from pathlib import Path
import tempfile
import json
import shutil
import sys
import os
import zipfile

from omega_kernel.amalgamation import inspect,extract
from omega_selfhost.bootstrap import tokenize,compile_source
from omega.modules import link
from omega_recursive.amalgamation import ROOT,OUTPUT,COMPONENTS,generate
from omega_platform.sandbox import c_tool,run,trusted
from omega_platform.budget import BUILD_BUDGET,COMPILER_BUDGET
from omega_native.codec import decode as native_decode


def test_all_six_components_in_one_reproducible_mixed_file():
    raw = OUTPUT.read_bytes()
    manifest,sources,prefix = inspect(raw)
    assert manifest['components'] == list(COMPONENTS)
    assert set(COMPONENTS) <= sources.keys()
    assert raw.decode() == generate()
    assert tokenize(raw.decode()) == tokenize(link('omega_singularity/main.omega',ROOT,dynamic=True).source)
    assert 'fn_principal' in compile_source(raw.decode())
    with tempfile.TemporaryDirectory() as tmp:
        destination = Path(tmp)/'sources'
        extract(raw,destination)
        for name in COMPONENTS:
            assert (destination/name).read_bytes() == sources[name]


def test_the_entire_mixed_file_compiles_and_executes_in_isolation(tmp_path):
    source = tmp_path/'mixed.c'
    source.write_text(compile_source(OUTPUT.read_text()))
    binary = tmp_path/'mixed'
    c_tool([shutil.which('cc'),'-std=gnu11','-O0','-DOMEGA_CRYPTO=1','-I',ROOT/'omega_selfhost',
            source,'-lgmp','-lcrypto','-o',binary],
           inputs=[source,ROOT/'omega_selfhost'],output_directory=tmp_path,budget=BUILD_BUDGET,check=True)
    envelope = {'operation':'induce','request':json.loads((ROOT/'omega_singularity/examples/induction.json').read_text())}
    request = tmp_path/'request.json'
    request.write_text(json.dumps(envelope))
    result = run([binary,request],readonly=[request],budget=COMPILER_BUDGET,check=True)
    data = native_decode(result.stdout.strip())
    assert data['training_error'] == data['holdout_error'] == 0
    assert result.sandboxed


def test_offline_wheel_delivers_all_six_components_without_neural_packages(tmp_path,monkeypatch):
    wheels = tmp_path/'wheels'
    trusted([sys.executable,'-m','build','--no-isolation','--wheel','--outdir',wheels],
            cwd=ROOT,budget=BUILD_BUDGET,check=True)
    wheel = next(wheels.glob('*.whl'))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert 'omega_recursive/omega_singularity.omega' in names
        assert 'omega_native/_sources/omega_gpu/parallel_induction.wgsl' in names
        for component in COMPONENTS:
            assert 'omega_native/_sources/'+component in names
    environment = tmp_path/'installed'
    trusted([sys.executable,'-m','venv',environment],budget=BUILD_BUDGET,check=True)
    python = environment/'bin/python'
    trusted([python,'-m','pip','install','--no-index','--no-deps',wheel],budget=BUILD_BUDGET,check=True)
    pinned = ROOT.parent/'.tools/bubblewrap-0.12.0/bin'
    if pinned.is_dir():
        monkeypatch.setenv('PATH',str(pinned)+os.pathsep+os.environ['PATH'])
    code = '''
from omega_recursive.runtime import call
from omega_recursive.certificates import certify_claim,verify_claim
from omega_recursive.amalgamation import OUTPUT,inspect
import importlib.util
r=call('universe',{'domain':'affine','seed':1,'tasks':1,'train':2,'heldout':1})
t=r['tasks'][0]
assert verify_claim(certify_claim({'format':'omega-epistemic-claim-1','dag':t['answer_key'],'observations':t['observations']}))['accepted']
assert len(inspect(OUTPUT.read_bytes())[0]['components'])==6
assert importlib.util.find_spec('torch') is None
assert importlib.util.find_spec('wgpu') is None
'''
    trusted([python,'-I','-c',code],cwd=tmp_path,budget=BUILD_BUDGET,check=True)
