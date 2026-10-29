"""Proof-gated generations, atomic selection and narrowly scoped Git publication."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from omega_selfhost.proof_protocol import encode
from omega_self_mutate.rules import validate_rule,install_template
from omega_self_mutate.bootstrap import evolve
from omega_self_mutate.activation import activate,audit_generation
from .bridge_lean_filter import verify_receipt


def _git(repo,*arguments):
    return subprocess.run(['git','-C',str(repo),*arguments],check=True,capture_output=True,text=True).stdout.strip()


def publish_generation(generation,*,repo=None,commit=False,replace_source=False,restart_runtime=None,_canonical_change=None):
    from omega_selfhost.driver import ROOT,PACKAGE
    repo=Path(repo or ROOT).resolve();generation=Path(generation).resolve()
    record=audit_generation(generation)
    source=repo/'omega_selfhost/compiler.omega';original=source.read_bytes()
    expected=install_template(original.decode(),record['rule']).encode()
    if original!=(PACKAGE/'compiler.omega').read_bytes() or (generation/'bootstrap/compiler.omega').read_bytes()!=expected:raise ValueError('Published pass does not match this canonical source')
    if commit:
        dirty=_git(repo,'status','--porcelain','--untracked-files=normal')
        own_change=(_canonical_change==original and not _git(repo,'diff','--cached','--name-only') and
                    _git(repo,'diff','--name-only')=='omega_selfhost/compiler.omega' and
                    not _git(repo,'ls-files','--others','--exclude-standard'))
        if dirty and not own_change:raise ValueError('Automatic commit requires a clean repository and index')
        if not replace_source:raise ValueError('Automatic source commits require explicit source replacement')
    state=repo/'build/selfhost';state.mkdir(parents=True,exist_ok=True)
    target=state/'active.json';old=target.read_bytes() if target.exists() else None
    epoch_path=state/'runtime-epoch.json';old_epoch=epoch_path.read_bytes() if epoch_path.exists() else None
    publication=repo/'omega_selfhost/evolved'/record['rule']['id']
    if commit and publication.exists():raise ValueError('Refusing to overwrite a published generation')
    paths=[];revision=None
    with (state/'.hyper-cycle.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:
            selector=activate(generation,selection_root=state)
            if replace_source:
                temporary=source.with_suffix('.hyper.tmp');temporary.write_bytes(expected);os.replace(temporary,source)
            if commit:
                publication.mkdir(parents=True)
                files={'compiler.omega':expected,'optimization.lean':(generation/'optimization.lean').read_bytes(),
                       'generation.json':encode({'format':'omega-published-mutation-1','rule_id':record['rule']['id'],
                          'base_sha256':hashlib.sha256(original).hexdigest(),'compiler_sha256':selector['binary_sha256'],
                          'objective':record['objective'],'proof_sha256':record['proof']['source_sha256']})}
                for name,data in files.items():(publication/name).write_bytes(data)
                paths=['omega_selfhost/compiler.omega',publication.relative_to(repo).as_posix()]
                _git(repo,'add','--',*paths)
                _git(repo,'commit','-m','Adopt verified Omega optimizer '+record['rule']['id'][:16],'--',*paths)
                revision=_git(repo,'rev-parse','HEAD')
            if restart_runtime is not None:restart_runtime(selector)
            epoch={'format':'omega-runtime-epoch-1','compiler_sha256':selector['binary_sha256'],
                   'generation':str(generation),'git_commit':revision,'source_replaced':replace_source}
            temporary=state/'.runtime-epoch.tmp';temporary.write_bytes(encode(epoch));os.replace(temporary,state/'runtime-epoch.json')
            if replace_source and not (state/'hyper-canonical.json').exists():
                baseline={'source':original.decode(),'sha256':hashlib.sha256(original).hexdigest()}
                temporary=state/'.hyper-canonical.tmp';temporary.write_bytes(encode(baseline));os.replace(temporary,state/'hyper-canonical.json')
            return epoch
        except BaseException:
            if revision is not None:_git(repo,'revert','--no-edit',revision)
            if replace_source:
                temporary=source.with_suffix('.hyper.tmp');temporary.write_bytes(original);os.replace(temporary,source)
            if old is None:target.unlink(missing_ok=True)
            else:
                temporary=state/'.rollback-active.tmp';temporary.write_bytes(old);os.replace(temporary,target)
            if old_epoch is None:epoch_path.unlink(missing_ok=True)
            else:
                temporary=state/'.rollback-epoch.tmp';temporary.write_bytes(old_epoch);os.replace(temporary,epoch_path)
            if paths and revision is None:_git(repo,'reset','--',*paths)
            raise


def evolve_from_receipt(lhs,receipt,proof_directory,output,*,public_key,install=False,commit=False,replace_source=False,restart_runtime=None,expected_source_sha256=None):
    if commit and not install:raise ValueError('A source commit requires installation')
    if replace_source and not install:raise ValueError('Source replacement requires installation')
    admitted=verify_receipt(receipt,proof_directory,public_key=public_key)
    rule=validate_rule(lhs,admitted['statement']['ast'])
    from omega_selfhost.driver import ROOT,PACKAGE
    from omega_self_mutate.activation import load_active
    state=ROOT/'build/selfhost';state.mkdir(parents=True,exist_ok=True)
    source=PACKAGE/'compiler.omega'
    with (state/'.hyper-evolution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        previous=source.read_bytes();base=previous
        if expected_source_sha256 is not None and hashlib.sha256(previous).hexdigest()!=expected_source_sha256:raise ValueError("Compiler changed before the locked bootstrap cycle")
        baseline=state/'hyper-canonical.json'
        if baseline.exists():
            if baseline.is_symlink() or not baseline.is_file() or baseline.stat().st_size>2*1024**2:raise ValueError('Invalid host canonical baseline')
            data=json.loads(baseline.read_text());base=data['source'].encode()
            if hashlib.sha256(base).hexdigest()!=data['sha256']:raise ValueError('Changed canonical baseline')
            if previous!=base:
                selected=load_active()
                if selected is None or (selected.parent/'compiler.omega').read_bytes()!=previous:raise ValueError('User compiler changes cannot be replaced by a curiosity cycle')
                if commit and _git(ROOT,'status','--porcelain','--untracked-files=normal'):raise ValueError('Automatic commit requires a clean repository and index')
                source.write_bytes(base)
        adopted=False
        try:
            generation=evolve(rule,output)
            root=Path(output);(root/'tier2-receipt.json').write_bytes(encode(receipt))
            if install:
                generation['runtime_epoch']=publish_generation(root,commit=commit,replace_source=replace_source,restart_runtime=restart_runtime,
                                                               _canonical_change=base if previous!=base else None)
                adopted=replace_source
            return generation
        finally:
            if previous!=base and not adopted:source.write_bytes(previous)


def propose_from_profile(profile):
    from omega_selfhost.driver import build
    from omega_platform.sandbox import run
    from omega_platform.budget import COMPILER_BUDGET
    with tempfile.TemporaryDirectory(prefix='omega-mutator-v2-') as temporary:
        root=Path(temporary);path=root/'profile.json';path.write_bytes(encode(profile));output=root/'proposal.json'
        binary=root/'mutator';build(Path(__file__).with_name('auto_mutator_v2.omega'),binary)
        run([binary,path,output],readonly=[path],writable=[root],budget=COMPILER_BUDGET,check=True)
        return json.loads(output.read_text())
