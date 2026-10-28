"""Atomic content-checked compiler selection in the existing checkout."""
import fcntl
import hashlib
import json
import os
import stat
from pathlib import Path
from .bootstrap import protected_hashes
from omega_selfhost.proof_protocol import encode


def state_root():return Path(__file__).resolve().parents[1]/'build/selfhost'


def regular(path,limit):
    metadata=path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size>limit:raise ValueError('Bounded regular generation artifact required')
    return path


def audit_generation(root):
    from .rules import validate_rule,install_template
    from omega_selfhost.driver import verify_optimization,bootstrap,BUILD,PACKAGE,cc
    root=Path(root).resolve();manifest=root/'generation.json'
    regular(manifest,8*1024**2)
    record=json.loads(manifest.read_text())
    if record.get('format')!='omega-self-mutation-1' or record['protected']!=protected_hashes():raise ValueError('Verifier boundary changed since generation')
    if type(record['files']) is not dict or not 1<=len(record['files'])<=64:raise ValueError('Generation artifact count budget exceeded')
    for relative,expected in record['files'].items():
        raw=root/relative;path=raw.resolve()
        if not path.is_relative_to(root):raise ValueError('Changed generation artifact')
        regular(raw,64*1024**2)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Changed generation artifact')
    admitted=validate_rule(record['rule']['lhs'],record['rule']['rhs'])
    expected=install_template((PACKAGE/'compiler.omega').read_text(),admitted)
    if (root/'bootstrap/compiler.omega').read_text()!=expected or record['compiler_relative']!='bootstrap/stage3':raise ValueError('Generation is not the admitted trusted compiler template')
    # Content hashes alone cannot authenticate a proposer-controlled manifest.
    # Independently lower the approved source with the canonical seed and
    # rebuild its executable before allowing it to become the compiler.
    import tempfile
    from omega_platform.sandbox import run
    from omega_platform.budget import COMPILER_BUDGET
    bootstrap(force=False)
    with tempfile.TemporaryDirectory(prefix='omega-mutation-audit-') as temporary:
        target=Path(temporary);source=target/'compiler.omega';source.write_text(expected)
        c=target/'compiler.c';binary=target/'compiler'
        run([BUILD/'omegac-stage2',source,c],readonly=[source],writable=[target],budget=COMPILER_BUDGET,check=True)
        cc(c,binary)
        for stage in range(4):
            if (root/f'bootstrap/stage{stage}.c').read_bytes()!=c.read_bytes() or (root/f'bootstrap/stage{stage}').read_bytes()!=binary.read_bytes():raise ValueError('Untrusted compiler binary or bootstrap stage')
        if (root/'bootstrap/stage4.c').read_bytes()!=c.read_bytes():raise ValueError('Untrusted bootstrap fixed point')
    witness=json.loads((root/'probe.c.opt.json').read_text());verify_optimization(witness)
    return record


def activate(root,*,selection_root=None):
    record=audit_generation(root);root=Path(root).resolve()
    target=Path(selection_root or state_root());target.mkdir(parents=True,exist_ok=True)
    binary=root/record['compiler_relative']
    if not binary.resolve().is_relative_to(root):raise ValueError('Compiler outside admitted generation')
    value={'format':'omega-active-compiler-1','generation':str(root),'manifest_sha256':hashlib.sha256((root/'generation.json').read_bytes()).hexdigest(),
           'binary':str(binary),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'protected':record['protected']}
    with (target/'.activation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        temporary=target/'.active.tmp';temporary.write_bytes(encode(value));os.replace(temporary,target/'active.json')
    return value


def load_active(*,selection_root=None):
    path=Path(selection_root or state_root())/'active.json'
    if not path.exists():return None
    regular(path,65536)
    value=json.loads(path.read_text())
    if value.get('format')!='omega-active-compiler-1' or value['protected']!=protected_hashes():raise ValueError('Active compiler verifier boundary changed')
    root=Path(value['generation']);binary=Path(value['binary'])
    regular(binary,64*1024**2)
    if binary.is_symlink() or not binary.resolve().is_relative_to(root.resolve()) or hashlib.sha256(binary.read_bytes()).hexdigest()!=value['binary_sha256']:
        raise ValueError('Active compiler bytes changed')
    manifest=root/'generation.json'
    regular(manifest,8*1024**2)
    if hashlib.sha256(manifest.read_bytes()).hexdigest()!=value['manifest_sha256']:raise ValueError('Active compiler admission changed')
    record=json.loads(manifest.read_text())
    for relative,expected in record['files'].items():
        artifact=root/relative
        regular(artifact,64*1024**2)
        if artifact.is_symlink() or not artifact.resolve().is_relative_to(root.resolve()) or hashlib.sha256(artifact.read_bytes()).hexdigest()!=expected:raise ValueError('Active generation artifact changed')
    return binary


def deactivate(*,selection_root=None):
    target=Path(selection_root or state_root());pointer=target/'active.json'
    if pointer.exists():os.replace(pointer,target/'previous-active.json')
