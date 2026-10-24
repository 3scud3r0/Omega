"""Content-addressed build records. Integrity is separate from authorization."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def sha256(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):result.update(block)
    return result.hexdigest()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()


def toolchain():
    from .budget import BUILD_BUDGET
    from .sandbox import trusted,IsolationUnavailable
    import os
    compiler=shutil.which(os.environ.get('CC','cc'))
    if not compiler:raise IsolationUnavailable('A trusted C compiler is required')
    compiler=Path(compiler).resolve()
    version=trusted([compiler,'--version'],budget=BUILD_BUDGET,check=True).stdout
    gmp=trusted([compiler,'-print-file-name=libgmp.so'],budget=BUILD_BUDGET,check=True).stdout.strip()
    if not Path(gmp).is_file():raise IsolationUnavailable('GMP shared library is required')
    headers={str(p):sha256(p) for p in [Path('/usr/include/gmp.h'),
               Path('/usr/include/x86_64-linux-gnu/gmp.h')] if p.is_file()}
    if not headers:raise IsolationUnavailable('GMP headers are required')
    from .sandbox import _tool
    supervision={name:{'path':str(Path(_tool(name)).resolve()),'sha256':sha256(_tool(name))}
                 for name in ('bwrap','prlimit')}
    return {'supervision':supervision,'cc':{'path':str(compiler),'sha256':sha256(compiler),'version':version.strip()},
            'gmp':{'library_sha256':sha256(gmp),'headers':headers},
            'flags':['-std=gnu11','-O2','-s','-lgmp']}


def compiler_inputs(root):
    root=Path(root)
    names=['omega_selfhost/compiler.omega','omega_selfhost/bootstrap.py',
           'omega_selfhost/driver.py','omega_selfhost/runtime.h',
           'omega_selfhost/tensor_runtime.h','omega_selfhost/polynomial.h',
           'omega_platform/manifest.py','omega_platform/budget.py','omega_platform/sandbox.py',
           'omega_platform/_supervisor.py']
    record={'sources':{n:sha256(root/n) for n in names},'toolchain':toolchain()}
    return {'sha256':hashlib.sha256(canonical(record)).hexdigest(),**record}


def artifact_record(paths,root):
    root=Path(root).resolve()
    result={}
    for path in paths:
        path=Path(path).resolve(strict=True)
        if not path.is_relative_to(root):raise ValueError('Artifact must be inside its declared root')
        if not path.is_file():raise ValueError('Artifact is not a regular file')
        result[str(path.relative_to(root))]={'sha256':sha256(path),'bytes':path.stat().st_size}
    return result


def verify(record,root):
    if record.get('format')!='omega-build-manifest-1':raise ValueError('Unknown build manifest')
    root=Path(root).resolve()
    for name,expected in record['artifacts'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file():raise ValueError('Missing or escaping artifact')
        if expected!={'sha256':sha256(path),'bytes':path.stat().st_size}:
            raise ValueError('Artifact integrity mismatch: '+name)
    for name,expected in record.get('sources',{}).items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or sha256(path)!=expected:
            raise ValueError('Source integrity mismatch: '+name)
    if 'compiler_inputs' in record:
        inputs=dict(record['compiler_inputs']);expected=inputs.pop('sha256')
        if hashlib.sha256(canonical(inputs)).hexdigest()!=expected:
            raise ValueError('Compiler input record integrity mismatch')
    return True


def build_manifest(root,paths):
    root=Path(root).resolve()
    # No environment, remote URL or credential is stored in provenance.
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
    changed=subprocess.run(['git','status','--porcelain','--untracked-files=normal'],cwd=root,
                           capture_output=True,text=True,check=True).stdout
    sources={}
    for folder in ('omega_selfhost','omega_platform','omega_nextorch','formal','requirements'):
        for path in sorted((root/folder).rglob('*')):
            if '.lake' in path.parts or '__pycache__' in path.parts:continue
            if path.is_file() and (path.suffix in ('.py','.h','.lean','.lock','.omega','.json') or path.name=='lean-toolchain'):
                sources[str(path.relative_to(root))]=sha256(path)
    from omega_selfhost.proof import lake_binary
    lake=lake_binary().resolve(strict=True)
    mathlib=root/'formal/tensor/.lake/packages/mathlib'
    mathlib_commit=subprocess.run(['git','rev-parse','HEAD'],cwd=mathlib,
                                 capture_output=True,text=True,check=True).stdout.strip()
    formal={'lake_sha256':sha256(lake),'lean_sha256':sha256(lake.with_name('lean')),
            'mathlib_commit':mathlib_commit}
    return {'format':'omega-build-manifest-1','commit':commit,'dirty':bool(changed),
            'formal_toolchain':formal,
            'sources':sources,'compiler_inputs':compiler_inputs(root),
            'artifacts':artifact_record(paths,root)}
