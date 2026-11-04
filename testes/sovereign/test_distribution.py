from pathlib import Path
import sys
import zipfile
from omega_platform.sandbox import trusted
from omega_platform.budget import BUILD_BUDGET
from omega_sovereign.native import ROOT


def test_wheel_builds_native_seeds_without_repository_sources(tmp_path):
    wheels=tmp_path/'wheels'
    result=trusted([sys.executable,'-m','build','--no-isolation','--wheel','--outdir',wheels],cwd=ROOT,budget=BUILD_BUDGET)
    assert result.ok,result.stderr
    wheel=next(wheels.glob('*.whl'))
    with zipfile.ZipFile(wheel) as archive:
        for name in ('sovereign/native/bigq.S','sovereign/native/compiler.S','sovereign/native/x25519.S',
                     'sovereign/native/sha3.S','sovereign/baremetal/boot.S','sovereign/omega/tcp.omega',
                     'sovereign/omega/raft.omega','hardware/sovereign/icestick.pcf','hardware/sovereign/sky130.json'):
            assert 'omega_native/_sources/'+name in archive.namelist()
    # Extract a wheel into an isolated import root. No system site packages,
    # repository path, executable compiler, GMP or Lean are used to make seeds.
    installed=tmp_path/'installed';installed.mkdir()
    with zipfile.ZipFile(wheel) as archive:archive.extractall(installed)
    code='''
import sys
sys.path.insert(0,sys.argv[1])
from omega_sovereign.native import build_seed,build_crypto,SOURCES
from omega_sovereign.baremetal import build
from pathlib import Path
assert '_sources' in str(SOURCES)
p=Path(sys.argv[2]);p.mkdir()
assert build_seed(p/'seed')['external_runtime_dependencies']==[]
assert not build_crypto(p/'crypto')['constant_time_x25519']
assert not build(p/'boot')['physical_hardware_validated']
'''
    result=trusted([sys.executable,'-I','-S','-c',code,installed,tmp_path/'output'],cwd=tmp_path,budget=BUILD_BUDGET)
    assert result.ok,result.stdout+result.stderr
