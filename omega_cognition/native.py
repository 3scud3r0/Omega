"""Source-bound native cognitive models; every request executes in OS isolation."""
from pathlib import Path
import fcntl
import tempfile
from omega.modules import link
from omega_kernel.runtime import _compile_native_chunks,digest
from omega_kernel.protocol import plain,sha256
from omega_recursive.runtime import data
from omega_native.codec import decode as native_decode
from omega_security.encoding import canonical,decode
from omega_selfhost.driver import compiler,cc
from omega_platform.sandbox import run
from omega_platform.budget import COMPILER_BUDGET
ROOT=Path(__file__).resolve().parents[1]


def build():
    source_root=ROOT if (ROOT/'ginasio.omega').is_file() else ROOT/'omega_native/_sources'
    program=link('omega_cognition/native/main.omega',source_root,dynamic=True)
    tool=compiler()
    inputs={name:digest(ROOT/name) for name in ('omega_cognition/native.py','omega_kernel/runtime.py',
           'omega_selfhost/runtime.h','omega_selfhost/native_std.h','omega_selfhost/memory.h',
           'omega_platform/sandbox.py','omega_platform/budget.py')}
    inputs['compiler']=digest(tool);inputs['bootstrap']=digest(tool.parent/'bootstrap.json')
    identity={'format':'omega-cognitive-models-1','modules':program.manifest(),'inputs':inputs}
    key=sha256(canonical(identity,max_bytes=4*1024**2,max_nodes=100000))
    folder=ROOT/'build/cognitive';folder.mkdir(parents=True,exist_ok=True)
    binary=folder/('models-'+key[:32]);record=binary.with_suffix('.json')
    with (folder/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if binary.exists() or record.exists() or binary.is_symlink() or record.is_symlink():
            if any(p.is_symlink() or not p.is_file() for p in (binary,record)):raise ValueError('Model cache integrity')
            info=decode(record.read_bytes(),max_bytes=4*1024**2,max_nodes=100000)
            if info!={'identity':identity,'binary_sha256':digest(binary)}:raise ValueError('Model cache integrity')
            return binary
        with tempfile.TemporaryDirectory(dir=folder) as tmp:
            stage=Path(tmp);c=_compile_native_chunks(program,tool,stage);out=stage/'program';cc(c,out)
            out.replace(binary)
            record.write_bytes(canonical({'identity':identity,'binary_sha256':digest(binary)},max_bytes=4*1024**2,max_nodes=100000))
    return binary


def call(operation,request,*,jail=None):
    if operation not in ('batch','transition','jail') or type(request) is not dict:raise ValueError('Cognitive request')
    payload=canonical({'operation':operation,'request':plain(request)},max_bytes=1024**2,max_nodes=50000,max_depth=32)
    binary=build()
    with tempfile.TemporaryDirectory(prefix='omega-sovereign-') as tmp:
        path=Path(tmp)/'request.json';path.write_bytes(payload)
        from omega_agent_sandbox.jail import Jail
        from omega_platform.sandbox import ExecutionFailure
        result=(jail or Jail()).execute([binary,path],readonly=[path])
        if not result.ok:raise ExecutionFailure(result)
    return data(native_decode(result.stdout.strip()))
