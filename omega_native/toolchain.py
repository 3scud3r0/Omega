from pathlib import Path
import hashlib,json,fcntl,subprocess,tempfile
from omega.modules import link
from omega_selfhost.driver import ROOT,compiler,cc
from omega_platform.sandbox import run, _limits, clean_environment
from omega_platform.budget import COMPILER_BUDGET


def build(entry='tools/native_suite.omega',destination=None):
    if entry not in ('tools/native_suite.omega','tools/repl.omega'):raise ValueError('Known native application entry required')
    source_root=ROOT if (ROOT/'std/math.omega').is_file() else Path(__file__).parent/'_sources'
    program=link(entry,source_root,dynamic=True)
    fingerprint=hashlib.sha256(program.source.encode()+b''.join((ROOT/name).read_bytes() for name in ('omega_selfhost/native_std.h','omega_selfhost/runtime.h','omega_selfhost/compiler.omega','omega_selfhost/driver.py','omega_platform/manifest.py'))).hexdigest()[:24]
    directory=ROOT/'build/native-stdlib';directory.mkdir(parents=True,exist_ok=True)
    target=Path(destination).resolve() if destination else directory/(Path(entry).stem+'-'+fingerprint)
    if destination and any(p.exists() or p.is_symlink() for p in (target,target.with_suffix('.c'),target.with_suffix('.modules.json'))):raise ValueError('Refusing to replace an existing native build artifact')
    target.parent.mkdir(parents=True,exist_ok=True)
    with (directory/'.build.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if not target.exists() or not target.with_suffix('.modules.json').is_file():
            with tempfile.TemporaryDirectory(prefix='.build-',dir=target.parent) as temporary:
                path=Path(temporary);source=path/'linked.omega';source.write_text(program.source);c=path/'program.c'
                run([compiler(),source,c],readonly=[source],writable=[path],budget=COMPILER_BUDGET,check=True)
                binary=path/'program';cc(c,binary)
                c.replace(target.with_suffix('.c'))
                target.with_suffix('.modules.json').write_bytes(json.dumps(program.manifest(),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
                binary.replace(target)
    return target


def execute(mode,request,*,readonly=(),writable=(),output_root=None,interactive=False,input_text=None):
    binary=build()
    with tempfile.TemporaryDirectory(prefix='omega-native-request-') as temporary:
        root=Path(temporary);path=root/'request.json';path.write_text(json.dumps(request,ensure_ascii=False,separators=(',',':'),allow_nan=False))
        argv=[binary,mode,path,*([Path(output_root).resolve()] if output_root else [])]
        if interactive or input_text is not None:
            result=subprocess.run(_limits(COMPILER_BUDGET)+list(map(str,argv)),input=input_text,text=True,capture_output=input_text is not None,check=True,timeout=COMPILER_BUDGET.wall_seconds,env=clean_environment(COMPILER_BUDGET))
            return result.stdout if input_text is not None else ''
        return run(argv,readonly=[path,*readonly],writable=list(writable),budget=COMPILER_BUDGET,check=True).stdout


def result(mode,request,**options):
    output=execute(mode,request,**options)
    return json.loads(output.strip().splitlines()[-1])
