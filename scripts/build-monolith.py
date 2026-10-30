#!/usr/bin/env python3
"""Reproduce a readable single-file source distribution without invented code.

Embedded sources are existing implementations, not 133 newly completed tasks.
Run with --check in CI to detect a stale or modified source distribution.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'omega/omega_3_monolith.py'
FOLDERS={'omega_engines','omega_core','omega_ml','ciencia','agentes_cientificos','omega_science','omega_live','omega_ingest','civilizacao_agentes','incubadora_continua','sociedade_hierarquica','metamorfose_cognitiva','fabrica_descobertas','imunologia_sistemica','infraestrutura_soberana','std','runtime','tools','omega_native','validation','omega_agent','omega_coder','omega_memory','omega_learning','omega_evolution','omega_tools','omega_security','omega_bench','omega','omega_open','omega_selfhost','omega_platform','omega_nextorch','nextorch',
         'omega_refine_check','omega_synth_mcts','omega_self_mutate','omega_agent_sandbox','omega_cognition','hardware',
         'omega_gpu_mcts','omega_abstract_domain','omega_autotelic','omega_self_evolve_v2','omega_runtime_verified',
         'formal','scripts','requirements','roadmap','docs','testes','exemplos','.github'}
EXTENSIONS={'.py','.h','.omega','.lean','.json','.lock','.tsv','.md','.sh','.yml','.c','.svg','.sv','.cu','.cuh','.cpp'}

LAUNCHER='''"""Readable single-file Omega source distribution.

This bundles existing code; line count is not acceptance of OM-018..OM-150.
No code is downloaded or candidates executed during extraction/verification.
The installed system prerequisites and Python dependencies are still required.
"""
from __future__ import annotations
import argparse
import ast
import ctypes
import errno
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import unittest

MAX_BYTES=16*1024*1024


def validated_sources():
    if len(SOURCES)>2000:
        raise ValueError('Source count budget exceeded')
    sources={};total=0
    for name,content in SOURCES:
        if type(name) is not str:
            raise ValueError('Malformed bundle path')
        path=PurePosixPath(name)
        if (type(name) is not str or not name or path.is_absolute() or
            str(path)!=name or any(part in ('.','..','.git') for part in path.parts) or
            ':' in name or chr(92) in name or name in sources):
            raise ValueError('Unsafe or duplicate bundle path')
        if type(content) is not str:
            raise ValueError('Malformed bundle source')
        data=content.encode('utf-8');total+=len(data)
        if total>MAX_BYTES:
            raise ValueError('Source byte budget exceeded')
        if MANIFEST['files'].get(name)!={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}:
            raise ValueError('Embedded source integrity mismatch: '+name)
        sources[name]=data
    if set(sources)!=set(MANIFEST['files']):
        raise ValueError('Incomplete source manifest')
    canonical=json.dumps(MANIFEST['files'],sort_keys=True,separators=(',',':')).encode()
    if hashlib.sha256(canonical).hexdigest()!=MANIFEST['tree_sha256']:
        raise ValueError('Source tree integrity mismatch')
    return sources


def verify():
    sources=validated_sources()
    for name,data in sources.items():
        if name.endswith('.py'):
            ast.parse(data.decode('utf-8'),filename=name)
    return {'format':'omega-single-file-1','files':len(sources),
            'source_bytes':sum(map(len,sources.values())),
            'embedded_code_lines':MANIFEST['embedded_code_lines'],
            'tree_sha256':MANIFEST['tree_sha256'],
            'all_150_tasks_accepted':False}


def _publish(stage,target):
    # Atomic and exclusive: rename must never replace a concurrently created
    # destination. Linux is also the supported sandbox platform.
    libc=ctypes.CDLL(None,use_errno=True)
    rename=getattr(libc,'renameat2',None)
    if rename is None:
        raise RuntimeError('Atomic exclusive publication requires Linux renameat2')
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    rename.restype=ctypes.c_int
    if rename(-100,os.fsencode(stage),-100,os.fsencode(target),1):
        error=ctypes.get_errno()
        if error==errno.EEXIST:
            raise FileExistsError('Destination already exists')
        raise OSError(error,os.strerror(error))


def extract(destination):
    sources=validated_sources()
    requested=Path(destination)
    parent=requested.parent.resolve(strict=True)
    if requested.name in ('','.','..'):
        raise ValueError('A fresh destination directory is required')
    target=parent/requested.name
    if target.exists() or target.is_symlink():
        raise FileExistsError('Destination already exists')
    stage=Path(tempfile.mkdtemp(prefix='.omega-source-',dir=parent))
    try:
        for name,data in sources.items():
            path=stage/name
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream:
                stream.write(data)
            path.chmod(0o644)
        _publish(stage,target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return target


def coverage():
    sources=validated_sources()
    progress=json.loads(sources['roadmap/progress.json'])
    statuses={item['id']:item['status'] for item in progress['tasks']}
    records=[]
    for line in sources['roadmap/tasks.tsv'].decode().splitlines():
        task,phase,title,acceptance=line.split(chr(9))
        if int(task[3:])>=18:
            records.append({'id':task,'phase':int(phase),'title':title,
                            'acceptance':acceptance,'status':statuses[task],
                            'accepted':False})
    return records


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['verify','extract','coverage','self-test','omega'])
    parser.add_argument('arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args(argv)
    if args.action=='extract':
        if len(args.arguments)!=1:
            parser.error('extract requires exactly one fresh destination')
        print(extract(args.arguments[0]));return 0
    if args.action=='verify':
        print(json.dumps(verify(),sort_keys=True));return 0
    if args.action=='coverage':
        print(json.dumps(coverage(),ensure_ascii=False,indent=2));return 0
    with tempfile.TemporaryDirectory(prefix='omega-single-file-') as tmp:
        root=extract(Path(tmp)/'source')
        if any(name.startswith('omega.') and name!=__name__ for name in sys.modules):
            raise RuntimeError('Launch this file in a fresh Python interpreter')
        package=sys.modules.get('omega')
        previous_path=list(package.__path__) if package is not None else None
        if package is not None:
            package.__path__=[str(root/'omega')]
        sys.path.insert(0,str(root))
        try:
            if args.action=='self-test':
                verify()
                module=importlib.import_module('omega.monolith_components')
                suite=unittest.defaultTestLoader.loadTestsFromTestCase(module.MonolithTests)
                result=unittest.TextTestRunner(verbosity=2).run(suite)
                return 0 if result.wasSuccessful() else 1
            # Explicitly requested application entry point. Candidate programs
            # remain subject to the bundled driver/sandbox/Lean requirements.
            cli=importlib.import_module('omega.cli')
            return cli.principal(args.arguments)
        finally:
            sys.path.remove(str(root))
            if package is not None:
                package.__path__=previous_path

'''


def build():
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    selected=[]
    for name in sorted(set(tracked)):
        path=Path(name)
        if not name or ROOT/path==OUTPUT or '.lake' in path.parts or '__pycache__' in path.parts:
            continue
        if name=='scripts/monolith-components.py.txt' or (path.parts[0] in FOLDERS and
            (path.suffix in EXTENSIONS or path.name=='lean-toolchain')) or name in {'setup.py','pyproject.toml','MANIFEST.in','README.md','LICENSE','banco_de_dados.omega','synthesis.omega','fitness.omega','civilizacao_agentes.omega','incubadora_continua.omega','ginasio.omega'}:
            selected.append(name)
    sources={name:(ROOT/name).read_bytes().decode('utf-8') for name in selected}
    # The virtual module lives only inside the requested single-file artifact.
    # Its source is maintained as a template for reproducible regeneration.
    sources['omega/monolith_components.py']=(ROOT/'scripts/monolith-components.py.txt').read_bytes().decode('utf-8')
    sources=dict(sorted(sources.items()))
    files={name:{'bytes':len(text.encode()),'sha256':hashlib.sha256(text.encode()).hexdigest()} for name,text in sources.items()}
    digest=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    code_lines=sum(len(content.splitlines()) for name,content in sources.items() if Path(name).suffix in {'.py','.h','.c','.omega','.lean'})
    manifest={'format':'omega-source-tree-1','files':files,'tree_sha256':digest,'embedded_code_lines':code_lines}
    output=[LAUNCHER,'MANIFEST = '+repr(manifest)+'\n\nSOURCES = (\n']
    for name,content in sources.items():
        output.append('    ('+repr(name)+',\n')
        for line in content.splitlines(keepends=True):
            output.append('        '+repr(line)+'\n')
        if not content:output.append("        ''\n")
        output.append('    ),\n')
    output.append(")\n\nif __name__ == '__main__':\n    raise SystemExit(main())\n")
    return ''.join(output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    result=build()
    if args.check:
        if OUTPUT.read_text()!=result:
            raise SystemExit('Single-file distribution is stale; run scripts/build-monolith.py')
    else:
        OUTPUT.write_text(result,encoding='utf-8')
    print(f'{len(result.splitlines())} physical lines: {OUTPUT.name}')
