"""Tool orchestration; all source compilation after stage zero is native Omega."""
from __future__ import annotations
import hashlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import tempfile
from dataclasses import replace

from omega_platform.budget import Budget,BUILD_BUDGET,COMPILER_BUDGET,PROOF_BUDGET
from omega_platform.sandbox import trusted,run as isolated_run,ExecutionFailure,IsolationUnavailable
from omega_platform.manifest import compiler_inputs,artifact_record

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent
BUILD = Path(os.environ.get('OMEGA_NATIVE_BUILD', str(ROOT / 'build' / 'selfhost')))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(argv, *, cwd=None, timeout=180):
    return trusted(argv,cwd=cwd,budget=replace(BUILD_BUDGET,wall_seconds=timeout),check=True).stdout


def cc(source, output, optimization='-O2'):
    compiler = shutil.which(os.environ.get('CC','cc'))
    if not compiler:
        raise IsolationUnavailable('A C compiler and GMP development headers are required')
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
    isolated_run([binaries[0],source,c1],readonly=[source],writable=[destination],budget=COMPILER_BUDGET,check=True)
    cc(c1,binaries[1])
    isolated_run([binaries[1],source,c2],readonly=[source],writable=[destination],budget=COMPILER_BUDGET,check=True)
    cc(c2,binaries[2])
    c3=destination/'stage3.c'
    isolated_run([binaries[2],source,c3],readonly=[source],writable=[destination],budget=COMPILER_BUDGET,check=True)
    hashes=[digest(p) for p in (c0,c1,c2,c3)]
    if len(set(hashes))!=1 or digest(binaries[1])!=digest(binaries[2]):
        raise RuntimeError('Bootstrap fixed point was not reached')
    report={'inputs':compiler_inputs(ROOT),'format':'omega-bootstrap-2','source_sha256':digest(source),
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
            if info.get('inputs')==compiler_inputs(ROOT) and \
               info.get('stage_binary_sha256',[None]*3)[2]==digest(binary):
                return info
        return _bootstrap(destination)


def compiler():
    bootstrap(force=False)
    return BUILD/'omegac-stage2'


def compile_ir(source, optimize=False):
    with tempfile.TemporaryDirectory(prefix='omega-ir-') as tmp:
        out=Path(tmp)/'ir.json'
        isolated_run([compiler(),Path(source).resolve(),out,
                      '--optimized-ir' if optimize else '--ir'],
                     readonly=[source],writable=[tmp],budget=COMPILER_BUDGET,check=True)
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
    outputs=[destination,destination.with_suffix('.c'),destination.with_suffix('.build.json')]
    if optimize:outputs.extend([destination.with_suffix('.opt.json'),destination.with_suffix('.opt.lean')])
    if any(path.exists() for path in outputs):
        raise ValueError('Destination already exists')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.omega-build-',dir=destination.parent) as tmp:
        src,exe=Path(tmp)/'program.c',Path(tmp)/'program'
        argv=[compiler(),Path(source).resolve(),src]
        if optimize:argv.append('--optimize')
        isolated_run(argv,readonly=[source],writable=[tmp],budget=COMPILER_BUDGET,check=True)
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
    provenance={'format':'omega-build-manifest-1','source_sha256':digest(source),
                'compiler_inputs':compiler_inputs(ROOT),
                'compiler_sha256':digest(BUILD/'omegac-stage2'),
                'artifacts':artifact_record([p for p in outputs if p!=destination.with_suffix('.build.json')],destination.parent)}
    destination.with_suffix('.build.json').write_text(json.dumps(provenance,indent=2)+'\n')
    return {'provenance':str(destination.with_suffix('.build.json')),
            'binary':str(destination),'sha256':digest(destination),
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
        raise IsolationUnavailable('Build the Lean tensor kernel with scripts/setup-native.sh')
    with tempfile.TemporaryDirectory(prefix='omega-native-admission-') as tmp:
        data=Path(tmp)/'result.json'
        data.write_text(json.dumps(result,ensure_ascii=False))
        response=json.loads(isolated_run([kernel,data],readonly=[data],threads=True,
                                        budget=PROOF_BUDGET,check=True).stdout)
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
        isolated_run([kernel,'--prove-opt',data,proof],readonly=[data],writable=[tmp],
                     threads=True,budget=PROOF_BUDGET,check=True)
        generated=proof.read_text()
        result=check_generated(generated)
    if proof_path is not None:
        Path(proof_path).write_text(generated)
    return result


def run(binary, *, destination=None,budget=Budget()):
    if destination is not None:
        target=Path(destination)
        outputs=[target,target.with_suffix('.lean'),target.with_suffix('.verification.json')]
        if any(path.exists() for path in outputs):raise ValueError('Result destination already exists')
    execution=isolated_run([Path(binary).resolve()],budget=budget,check=True)
    result=json.loads(execution.stdout)
    optimization=Path(binary).resolve().with_suffix('.opt.json')
    if optimization.is_file():result['optimization']=json.loads(optimization.read_text())
    proof_path=Path(destination).with_suffix('.lean') if destination else None
    verification=verify_result(result,proof_path=proof_path)
    verification['execution']={'sandboxed':execution.sandboxed,'budget':execution.budget,
                               'wall_seconds':execution.wall_seconds}
    if destination is not None:
        target=Path(destination)
        if target.exists():raise ValueError('Result file already exists')
        target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
        target.with_suffix('.verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    return result,verification


def compiler_main():
    import argparse
    import sys
    parser=argparse.ArgumentParser(prog='omegac')
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('mode',nargs='?',choices=['--ir','--optimized-ir','--optimize'])
    # Flags remain compatible with the native compiler's final positional mode.
    parser.add_argument('--ir',action='store_true')
    parser.add_argument('--optimized-ir',action='store_true')
    parser.add_argument('--optimize',action='store_true')
    args=parser.parse_args()
    modes=[m for m,v in [('--ir',args.ir),('--optimized-ir',args.optimized_ir),
                          ('--optimize',args.optimize)] if v]
    if args.mode:modes.append(args.mode)
    if len(modes)>1:parser.error('Choose one output mode')
    destination=args.destination.resolve()
    outputs=[destination]
    if modes and modes[0]!='--ir':outputs.append(Path(str(destination)+'.opt.json'))
    if any(p.exists() for p in outputs):parser.error('Destination already exists')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.omega-compile-',dir=destination.parent) as tmp:
        out=Path(tmp)/'output'
        result=isolated_run([compiler(),args.source.resolve(),out,*modes],
                            readonly=[args.source],writable=[tmp],budget=COMPILER_BUDGET)
        sys.stdout.write(result.stdout);sys.stderr.write(result.stderr)
        if result.ok:
            os.replace(out,destination)
            if modes and modes[0]!='--ir':os.replace(Path(str(out)+'.opt.json'),outputs[1])
        return result.returncode if result.returncode>=0 else 128-result.returncode
