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
from omega_platform.sandbox import trusted,run as isolated_run,ExecutionFailure,IsolationUnavailable,c_tool
from omega_platform.manifest import compiler_inputs,artifact_record

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent
BUILD = Path(os.environ.get('OMEGA_NATIVE_BUILD', str(ROOT / 'build' / 'selfhost')))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(argv, *, cwd=None, timeout=180):
    return trusted(argv,cwd=cwd,budget=replace(BUILD_BUDGET,wall_seconds=timeout),check=True).stdout


def cc(source, output, optimization='-O2', *, static=False):
    if optimization not in ('-O0','-O1','-O2','-O3','-Os'):raise ValueError('Unsupported optimization level')
    compiler = shutil.which(os.environ.get('CC','cc'))
    if not compiler:
        raise IsolationUnavailable('A C compiler and GMP development headers are required')
    if type(static) is not bool:raise ValueError('Static linking must be boolean')
    c_tool([compiler,'-std=gnu11',optimization,*(['-static'] if static else []),'-s','-Wall','-Wextra',
             '-Wno-unused-function','-Wno-unused-variable','-Wno-misleading-indentation',
             '-I',PACKAGE,Path(source).resolve(),'-lgmp','-o',Path(output).resolve()],
            inputs=[source,PACKAGE],output_directory=Path(output).resolve().parent,
            budget=BUILD_BUDGET,check=True)


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
    from omega_self_mutate.activation import load_active
    selected=load_active()
    if selected is not None:return selected
    bootstrap(force=False)
    return BUILD/'omegac-stage2'


def source_types(source):
    """Independent, bounded static pass before native candidate compilation."""
    from omega.typesystem import infer_program
    from omega.procedural_types import infer_procedural
    source=Path(source)
    if not source.is_file():raise ValueError('Type inference requires a regular source file')
    with source.open(encoding='utf-8') as stream:text=stream.read(256*1024+1)
    from omega_refine_check.compiler import is_refined
    if is_refined(text):
        from omega_refine_check.syntax import lower
        return infer_program(lower(text)['source'])
    position=0
    while position<len(text):
        if text[position] in ' \t\r\n':position+=1
        elif text[position]=='#' or text.startswith('//',position):
            end=text.find('\n',position)
            if end<0:break
            position=end+1
        else:break
    end=position+6
    if text.startswith('funcao',position) and (end==len(text) or not (text[end].isalnum() or text[end]=='_')):
        return infer_procedural(text)
    return infer_program(text)


def compile_ir(source, optimize=False):
    from omega_refine_check.compiler import is_refined
    if is_refined(Path(source).read_text()):
        from omega_refine_check.contracts import check_program
        proof=check_program(Path(source).read_text())
        with tempfile.TemporaryDirectory(prefix='omega-refined-ir-') as temporary:
            lowered=Path(temporary)/'lowered.omega';lowered.write_text(proof['metadata']['source'])
            return compile_ir(lowered,optimize)
    with tempfile.TemporaryDirectory(prefix='omega-ir-') as tmp:
        out=Path(tmp)/'ir.json'
        isolated_run([compiler(),Path(source).resolve(),out,
                      '--optimized-ir' if optimize else '--ir'],
                     readonly=[source],writable=[tmp],budget=COMPILER_BUDGET,check=True)
        ir=json.loads(out.read_text())
        from omega.typed_ir import validate_legacy
        validate_legacy(ir)
        types=source_types(source)
        if types is not None:
            expected={name:list(t.shape) for name,t in types.symbols.items()}
            actual={name:ir['nos'][i]['forma'] for name,i in ir['simbolos'].items()}
            if expected!=actual:raise ValueError('Native IR types disagree with independent inference')
        return ir


def compile_text(source):
    with tempfile.TemporaryDirectory(prefix='omega-source-') as tmp:
        path=Path(tmp)/'input.omega'
        path.write_text(source,encoding='utf-8')
        try:
            return compile_ir(path)
        except RuntimeError as exc:
            from omega.sintaxe import ErroOmega
            raise ErroOmega(str(exc)) from exc


def build(source, destination, optimize=False, *, optimization='-O2', static=False):
    from omega_refine_check.compiler import is_refined
    if is_refined(Path(source).read_text()):
        from omega_refine_check.compiler import build as refined_build
        return refined_build(source,destination,optimize=optimize,optimization=optimization,static=static)
    destination=Path(destination).resolve()
    outputs=[destination,destination.with_suffix('.c'),destination.with_suffix('.build.json')]
    if optimize:outputs.extend([destination.with_suffix('.opt.json'),destination.with_suffix('.opt.lean')])
    if len(set(outputs))!=len(outputs):raise ValueError('Artifact destinations must be distinct')
    if any(path.exists() for path in outputs):
        raise ValueError('Destination already exists')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.omega-build-',dir=destination.parent) as tmp:
        src,exe=Path(tmp)/'program.c',Path(tmp)/'program'
        argv=[compiler(),Path(source).resolve(),src]
        if optimize:argv.append('--optimize')
        isolated_run(argv,readonly=[source],writable=[tmp],budget=COMPILER_BUDGET,check=True)
        inferred=source_types(source)
        cc(src,exe,optimization=optimization,static=static)
        optimization_certificate=None
        if optimize:
            optimization_certificate=json.loads(Path(str(src)+'.opt.json').read_text())
            verify_optimization(optimization_certificate,
                                proof_path=Path(tmp)/'optimization.lean')
        os.replace(src,destination.with_suffix('.c'))
        os.replace(exe,destination)
        if optimization_certificate is not None:
            destination.with_suffix('.opt.json').write_text(json.dumps(optimization_certificate,indent=2)+'\n')
            os.replace(Path(tmp)/'optimization.lean',destination.with_suffix('.opt.lean'))
    provenance={'format':'omega-build-manifest-1','source_sha256':digest(source),
                'native_c_flags':['-std=gnu11',optimization,*(['-static'] if static else []),'-s','-lgmp'],
                'inferred_types':inferred.to_dict() if inferred else None,
                'compiler_inputs':compiler_inputs(ROOT),
                'compiler_sha256':digest(compiler()),
                'artifacts':artifact_record([p for p in outputs if p!=destination.with_suffix('.build.json')],destination.parent)}
    destination.with_suffix('.build.json').write_text(json.dumps(provenance,indent=2)+'\n')
    return {'types':inferred.to_dict() if inferred else None,
            'provenance':str(destination.with_suffix('.build.json')),
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
    synthesized=None
    checked_result=result
    if result.get('optimization',{}).get('formato')=='omega-opt-cert-2':
        if result['optimization']['otimizado']!=result['ir']:raise ValueError('Synthesized optimization proves another graph')
        synthesized=verify_optimization(result['optimization'])
        checked_result={k:v for k,v in result.items() if k!='optimization'}
    with tempfile.TemporaryDirectory(prefix='omega-native-admission-') as tmp:
        data=Path(tmp)/'result.json'
        data.write_text(json.dumps(checked_result,ensure_ascii=False))
        response=json.loads(isolated_run([kernel,data],readonly=[data],threads=True,
                                        budget=PROOF_BUDGET,check=True).stdout)
        if not response.get('valid') or response['certificates']!=len(others) or \
           response.get('universal_identities')!=len(identity):
            raise ValueError('Lean kernel did not confirm all tensor certificates')
    optimization=synthesized or (verify_optimization(result['optimization']) if 'optimization' in result else None)
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
        mode='--prove-map' if certificate.get('formato')=='omega-opt-cert-2' else '--prove-opt'
        isolated_run([kernel,mode,data,proof],readonly=[data],writable=[tmp],
                     threads=True,budget=PROOF_BUDGET,check=True)
        generated=proof.read_text()
        result=check_generated(generated)
    if proof_path is not None:
        Path(proof_path).write_text(generated)
    return result


def run(binary, *, destination=None,budget=Budget()):
    # Preserve exception classes for legacy callers while sharing the checked
    # implementation. New callers can inspect Err without losing its stage.
    from omega_platform.results import Err
    result=run_checked(binary,destination=destination,budget=budget)
    if isinstance(result,Err) and result.cause is not None:raise result.cause
    return result.unwrap()


def build_checked(source,destination,optimize=False):
    from omega_platform.results import attempt,Err
    typed=attempt('types',source_types,source)
    if isinstance(typed,Err):return typed
    return attempt('build',build,source,destination,optimize)


def compile_ir_checked(source,optimize=False):
    from omega_platform.results import attempt,Err
    typed=attempt('types',source_types,source)
    if isinstance(typed,Err):return typed
    return attempt('ir',compile_ir,source,optimize)


def run_checked(binary,*,destination=None,budget=Budget()):
    """Tagged preflight, execution, proof and optional artifact-write results."""
    from omega_platform.results import attempt,Ok,Err
    def preflight():
        if destination is not None:
            target=Path(destination)
            outputs=[target,target.with_suffix('.lean'),target.with_suffix('.verification.json')]
            if len(set(outputs))!=len(outputs):raise ValueError('Result destinations must be distinct')
            if any(path.exists() for path in outputs):raise FileExistsError('Result destination already exists')
    ready=attempt('io',preflight)
    if isinstance(ready,Err):return ready
    def execute():
        generic=_generic_program(binary)
        execution=isolated_run([Path(binary).resolve()],budget=budget,check=True)
        data=json.loads(execution.stdout)
        optimization=Path(binary).resolve().with_suffix('.opt.json')
        if optimization.is_file():data['optimization']=json.loads(optimization.read_text())
        if generic is not None:
            from omega.generics import project_result
            data=project_result(generic,data)
        return execution,data
    execution=attempt('execute',execute)
    if isinstance(execution,Err):return execution
    status,data=execution.unwrap()
    proof_path=Path(destination).with_suffix('.lean') if destination else None
    checked=attempt('proof',verify_result,data,proof_path=proof_path)
    if isinstance(checked,Err):return checked
    verification=checked.unwrap()
    verification['execution']={'sandboxed':status.sandboxed,'budget':status.budget,'wall_seconds':status.wall_seconds}
    def publish():
        if destination is not None:
            target=Path(destination)
            with target.open('x',encoding='utf-8') as stream:stream.write(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
            with target.with_suffix('.verification.json').open('x',encoding='utf-8') as stream:stream.write(json.dumps(verification,indent=2)+'\n')
    published=attempt('io',publish)
    if isinstance(published,Err):return published
    return Ok((data,verification))


def build_module(entry,destination,*,root=None):
    from omega.modules import link
    from omega_platform.manifest import canonical
    entry=Path(entry)
    if root is None:
        entry=entry.resolve();root=entry.parent
    linked=link(entry,root)
    destination=Path(destination).resolve()
    module_source=destination.with_suffix('.linked.omega');module_manifest=destination.with_suffix('.modules.json')
    outputs=[destination,destination.with_suffix('.c'),destination.with_suffix('.build.json'),module_source,module_manifest]
    if len(set(outputs))!=len(outputs):raise ValueError('Module artifact destinations must be distinct')
    if any(path.exists() for path in outputs):raise FileExistsError('Module artifact destination already exists')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.omega-modules-',dir=destination.parent) as tmp:
        source=Path(tmp)/'linked.omega';source.write_text(linked.source,encoding='utf-8')
        result=build_checked(source,destination).unwrap()
    with module_source.open('x',encoding='utf-8') as stream:stream.write(linked.source)
    with module_manifest.open('xb') as stream:stream.write(canonical(linked.manifest()))
    record=destination.with_suffix('.build.json');provenance=json.loads(record.read_text())
    provenance.update(module_graph=linked.manifest(),module_source=module_source.name,module_manifest=module_manifest.name)
    provenance['artifacts'].update(artifact_record([module_source,module_manifest],destination.parent))
    record.write_text(json.dumps(provenance,indent=2,ensure_ascii=False)+'\n')
    return {**result,'modules':len(linked.manifest()['modules']),'linked_source':str(module_source),'module_manifest':str(module_manifest)}


def _bounded_text(path,limit):
    with Path(path).open('rb') as stream:data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('Generic artifact byte budget exceeded')
    return data.decode('utf-8')


def build_generic(source,templates,destination,*,limits=None):
    from omega.generics import Registry,expand,ExpansionLimits
    from omega_platform.manifest import canonical
    original=_bounded_text(source,1024*1024)
    template_text=_bounded_text(templates,1024*1024)
    program=expand(original,Registry.from_bytes(template_text.encode('utf-8')),
                   limits=ExpansionLimits() if limits is None else limits)
    destination=Path(destination).resolve()
    additions={'.generic-input.omega':original,'.generic-templates.json':template_text,
               '.expanded.omega':program.source,'.generics.json':canonical(program.manifest()).decode()}
    outputs=[destination,destination.with_suffix('.c'),destination.with_suffix('.build.json'),
             *(destination.with_suffix(suffix) for suffix in additions)]
    if len(set(outputs))!=len(outputs):raise ValueError('Generic artifact paths must be distinct')
    if any(path.exists() for path in outputs):raise FileExistsError('Generic artifact destination already exists')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.omega-generic-',dir=destination.parent) as tmp:
        expanded=Path(tmp)/'expanded.omega';expanded.write_text(program.source,encoding='utf-8')
        result=build_checked(expanded,destination).unwrap()
    for suffix,content in additions.items():
        with destination.with_suffix(suffix).open('x',encoding='utf-8') as stream:stream.write(content)
    path=destination.with_suffix('.build.json');record=json.loads(path.read_text())
    record['generic_expansion']=program.manifest()
    record['artifacts'].update(artifact_record([destination.with_suffix(s) for s in additions],destination.parent))
    path.write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
    return {**result,'generic_instances':len(program.manifest()['instances']),
            'expansion_manifest':str(destination.with_suffix('.generics.json'))}


def _generic_program(binary):
    from omega.generics import Registry,expand,ExpansionLimits
    from omega_platform.manifest import verify,canonical
    binary=Path(binary).resolve();manifest=binary.with_suffix('.generics.json')
    if not manifest.exists():
        record_path=binary.with_suffix('.build.json')
        if record_path.exists() and 'generic_expansion' in json.loads(_bounded_text(record_path,16*1024*1024)):
            raise ValueError('Missing required generic expansion manifest')
        return None
    record=json.loads(_bounded_text(binary.with_suffix('.build.json'),16*1024*1024))
    verify(record,binary.parent)
    required=[binary.with_suffix(s).name for s in ('.generic-input.omega','.generic-templates.json','.expanded.omega','.generics.json')]
    if not set(required)<=set(record['artifacts']):raise ValueError('Missing generic provenance artifacts')
    recorded=record.get('generic_expansion',{})
    limits=ExpansionLimits(**recorded.get('limits',{}))
    program=expand(_bounded_text(binary.with_suffix('.generic-input.omega'),1024*1024),
                   Registry.load(binary.with_suffix('.generic-templates.json')),limits=limits)
    expected=canonical(program.manifest())
    if manifest.read_bytes()!=expected or canonical(record.get('generic_expansion'))!=expected:
        raise ValueError('Generic expansion cannot be reproduced')
    if binary.with_suffix('.expanded.omega').read_bytes()!=program.source.encode():
        raise ValueError('Generic expanded source mismatch')
    return program


def generic_ir(source,templates,*,limits=None):
    from omega.generics import Registry,expand,project_ir,ExpansionLimits
    program=expand(_bounded_text(source,1024*1024),Registry.load(templates),
                   limits=ExpansionLimits() if limits is None else limits)
    with tempfile.TemporaryDirectory(prefix='omega-generic-ir-') as tmp:
        path=Path(tmp)/'expanded.omega';path.write_text(program.source,encoding='utf-8')
        return project_ir(program,compile_ir(path))


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
