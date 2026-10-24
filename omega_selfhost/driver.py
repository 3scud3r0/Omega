"""Tool orchestration; all source compilation after stage zero is native Omega."""
from __future__ import annotations
import hashlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent
BUILD = Path(os.environ.get('OMEGA_NATIVE_BUILD', str(ROOT / 'build' / 'selfhost')))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(argv, *, cwd=None, timeout=180):
    result = subprocess.run([str(a) for a in argv], cwd=cwd, capture_output=True,
                            text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Command failed: ' + str(argv[0]) + '\n' +
                           (result.stderr + result.stdout)[-8000:])
    return result.stdout


def cc(source, output, optimization='-O2'):
    compiler = shutil.which(os.environ.get('CC','cc'))
    if not compiler:
        raise RuntimeError('A C compiler and GMP development headers are required')
    command([compiler,'-std=gnu11',optimization,'-s','-Wall','-Wextra',
             '-Wno-unused-function','-Wno-unused-variable','-Wno-misleading-indentation',
             '-I',PACKAGE,source,'-lgmp','-o',output], timeout=300)


def _bootstrap(destination):
    from .bootstrap import compile_source
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=True)
    source=PACKAGE/'compiler.omega'
    c0,c1,c2=[destination/f'stage{i}.c' for i in range(3)]
    binaries=[destination/f'omegac-stage{i}' for i in range(3)]
    c0.write_text(compile_source(source.read_text(encoding='utf-8')),encoding='utf-8')
    cc(c0,binaries[0])
    command([binaries[0],source,c1])
    cc(c1,binaries[1])
    command([binaries[1],source,c2])
    cc(c2,binaries[2])
    c3=destination/'stage3.c'
    command([binaries[2],source,c3])
    hashes=[digest(p) for p in (c0,c1,c2,c3)]
    if len(set(hashes))!=1 or digest(binaries[1])!=digest(binaries[2]):
        raise RuntimeError('Bootstrap fixed point was not reached')
    report={'format':'omega-bootstrap-2','source_sha256':digest(source),
            'runtime_sha256':digest(PACKAGE/'runtime.h'),
            'stage_c_sha256':hashes,'stage_binary_sha256':[digest(p) for p in binaries],
            'fixed_point':True,'native_stages_use_python':False}
    (destination/'bootstrap.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def bootstrap(destination=BUILD, *, force=True):
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=True)
    with (destination/'.bootstrap.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        manifest=destination/'bootstrap.json'
        binary=destination/'omegac-stage2'
        if not force and manifest.is_file() and binary.is_file():
            info=json.loads(manifest.read_text())
            if info.get('source_sha256')==digest(PACKAGE/'compiler.omega') and \
               info.get('runtime_sha256')==digest(PACKAGE/'runtime.h') and \
               info['stage_binary_sha256'][2]==digest(binary):
                return info
        return _bootstrap(destination)


def compiler():
    bootstrap(force=False)
    return BUILD/'omegac-stage2'


def compile_ir(source, optimize=False):
    with tempfile.TemporaryDirectory(prefix='omega-ir-') as tmp:
        out=Path(tmp)/'ir.json'
        command([compiler(),Path(source).resolve(),out,
                 '--optimized-ir' if optimize else '--ir'])
        return json.loads(out.read_text())


def compile_text(source):
    with tempfile.TemporaryDirectory(prefix='omega-source-') as tmp:
        path=Path(tmp)/'input.omega'
        path.write_text(source,encoding='utf-8')
        try:
            return compile_ir(path)
        except RuntimeError as exc:
            from omega.sintaxe import ErroOmega
            raise ErroOmega(str(exc)) from exc


def build(source, destination, optimize=False):
    destination=Path(destination).resolve()
    outputs=[destination,destination.with_suffix('.c')]
    if optimize:outputs.extend([destination.with_suffix('.opt.json'),destination.with_suffix('.opt.lean')])
    if any(path.exists() for path in outputs):
        raise ValueError('Destination already exists')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.omega-build-',dir=destination.parent) as tmp:
        src,exe=Path(tmp)/'program.c',Path(tmp)/'program'
        argv=[compiler(),Path(source).resolve(),src]
        if optimize:argv.append('--optimize')
        command(argv)
        cc(src,exe)
        optimization=None
        if optimize:
            optimization=json.loads(Path(str(src)+'.opt.json').read_text())
            verify_optimization(optimization,
                                proof_path=Path(tmp)/'optimization.lean')
        os.replace(src,destination.with_suffix('.c'))
        os.replace(exe,destination)
        if optimization is not None:
            destination.with_suffix('.opt.json').write_text(json.dumps(optimization,indent=2)+'\n')
            os.replace(Path(tmp)/'optimization.lean',destination.with_suffix('.opt.lean'))
    return {'binary':str(destination),'sha256':digest(destination),
            'compiler':'self-hosted-omega-stage2','optimized':optimize}


def verify_result(result, *, proof_path=None):
    from .proof import check_identities
    if result.get('format')!='omega-native-result-2':
        raise ValueError('Unsupported native result format')
    identity=[c for c in result['certificates'] if c.get('tipo')=='identidade_nativa']
    others=[c for c in result['certificates'] if c.get('tipo')!='identidade_nativa']
    kernel=Path(os.environ.get('OMEGA_TENSOR_KERNEL',
                str(ROOT/'formal/tensor/.lake/build/bin/omega_tensor_kernel')))
    if not kernel.is_file():
        raise RuntimeError('Build the Lean tensor kernel with scripts/setup-native.sh')
    with tempfile.TemporaryDirectory(prefix='omega-native-admission-') as tmp:
        data=Path(tmp)/'result.json'
        data.write_text(json.dumps(result,ensure_ascii=False))
        response=json.loads(command([kernel,data],timeout=180))
        if not response.get('valid') or response['certificates']!=len(others) or \
           response.get('universal_identities')!=len(identity):
            raise ValueError('Lean kernel did not confirm all tensor certificates')
    optimization=verify_optimization(result['optimization']) if 'optimization' in result else None
    proof=check_identities(identity,proof_path=proof_path) if identity else None
    return {'valid':True,'tensor_certificates':len(others),
            'universal_identities':len(identity),'lean':response,'proof':proof,
            'optimization':optimization}


def verify_optimization(certificate, *, proof_path=None):
    from .proof import check_generated
    kernel=Path(os.environ.get('OMEGA_TENSOR_KERNEL',
                str(ROOT/'formal/tensor/.lake/build/bin/omega_tensor_kernel')))
    if not kernel.is_file():raise RuntimeError('Lean tensor kernel is required for optimization')
    with tempfile.TemporaryDirectory(prefix='omega-optimization-') as tmp:
        data=Path(tmp)/'cert.json';data.write_text(json.dumps(certificate))
        proof=Path(tmp)/'Optimization.lean'
        command([kernel,'--prove-opt',data,proof])
        generated=proof.read_text()
        result=check_generated(generated)
    if proof_path is not None:
        Path(proof_path).write_text(generated)
    return result


def run(binary, *, destination=None):
    if destination is not None:
        target=Path(destination)
        outputs=[target,target.with_suffix('.lean'),target.with_suffix('.verification.json')]
        if any(path.exists() for path in outputs):raise ValueError('Result destination already exists')
    result=json.loads(command([Path(binary).resolve()]))
    optimization=Path(binary).resolve().with_suffix('.opt.json')
    if optimization.is_file():result['optimization']=json.loads(optimization.read_text())
    proof_path=Path(destination).with_suffix('.lean') if destination else None
    verification=verify_result(result,proof_path=proof_path)
    if destination is not None:
        target=Path(destination)
        if target.exists():raise ValueError('Result file already exists')
        target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
        target.with_suffix('.verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    return result,verification


def compiler_main():
    import sys
    # The launcher is optional; the stage-2 executable accepts the same arguments.
    os.execv(compiler(),[str(compiler()),*sys.argv[1:]])
