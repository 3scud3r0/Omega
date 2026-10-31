"""Native Omega execution with source-bound caching and existing OS isolation."""
from pathlib import Path
import fcntl
import tempfile

from omega.modules import link
from omega_native.codec import decode as native_decode
from omega_platform.budget import COMPILER_BUDGET, Budget
from omega_platform.sandbox import run as isolated_run
from omega_security.encoding import canonical, decode
from omega_kernel.protocol import plain, sha256
from omega_kernel.runtime import _compile_native_chunks, digest
from omega_selfhost.driver import compiler, cc

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT if (ROOT/'omega_singularity/main.omega').is_file() else ROOT/'omega_native/_sources'
OPERATIONS = frozenset({'dag','induce','improve','universe','quarantine','sieve','verify','compile'})


def data(value):
    """Native tagged rationals -> exact, bounded JSON protocol values."""
    from fractions import Fraction
    if type(value) is Fraction:
        return value.numerator if value.denominator == 1 else str(value)
    if type(value) is dict:
        return {key: data(item) for key, item in value.items()}
    if type(value) is list:
        return [data(item) for item in value]
    return value


def build():
    program = link('omega_singularity/main.omega', SOURCE_ROOT, dynamic=True)
    tool = compiler()
    inputs = {name: digest(ROOT/name) for name in (
        'omega_recursive/runtime.py','omega_kernel/runtime.py',
        'omega_selfhost/runtime.h','omega_selfhost/native_std.h','omega_selfhost/memory.h',
        'omega_platform/sandbox.py','omega_platform/budget.py')}
    inputs['compiler'] = digest(tool)
    inputs['bootstrap'] = digest(tool.parent/'bootstrap.json')
    identity = {'format':'omega-recursive-build-1','modules':program.manifest(),'inputs':inputs}
    subject = sha256(canonical(identity,max_bytes=4*1024**2,max_nodes=100000))
    folder = ROOT/'build/recursive'
    folder.mkdir(parents=True,exist_ok=True)
    target = folder/('native-'+subject[:32])
    record_path = target.with_suffix('.json')
    with (folder/'.build.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if target.exists() or target.is_symlink() or record_path.exists() or record_path.is_symlink():
            if any(p.is_symlink() or not p.is_file() for p in (target,record_path)):
                raise ValueError('Incomplete or redirected recursive build cache')
            record = decode(record_path.read_bytes(),max_bytes=4*1024**2,max_nodes=100000)
            if record.get('identity') != identity or record.get('binary_sha256') != digest(target):
                raise ValueError('Modified recursive build cache')
            return target
        with tempfile.TemporaryDirectory(prefix='.recursive-',dir=folder) as tmp:
            stage = Path(tmp)
            source = _compile_native_chunks(program,tool,stage)
            binary = stage/'program'
            cc(source,binary)
            record = {'identity':identity,'binary_sha256':digest(binary),'subject_sha256':subject}
            binary.replace(target)
            with record_path.open('xb') as stream:
                stream.write(canonical(record,max_bytes=4*1024**2,max_nodes=100000))
    return target


def call(operation, request, *, budget=COMPILER_BUDGET):
    if operation not in OPERATIONS or type(request) is not dict or type(budget) is not Budget:
        raise ValueError('Known recursive operation, exact request object and OS budget required')
    payload = canonical({'operation':operation,'request':plain(request)},
                        max_bytes=4*1024**2,max_nodes=60000,max_depth=44)
    binary = build()
    with tempfile.TemporaryDirectory(prefix='omega-recursive-') as tmp:
        path = Path(tmp)/'request.json'
        path.write_bytes(payload)
        result = isolated_run([binary,path],readonly=[path],budget=budget)
    if not result.ok:
        raise RuntimeError('Native recursive request failed: '+result.stderr[-2000:])
    return data(native_decode(result.stdout.strip()))
