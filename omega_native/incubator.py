"""Bounded proposal -> native automatic approval -> verified bootstrap.

Approval mode is a supervisor option, never read from the candidate proposal.
There is no background daemon installed and no proof bypass in automatic mode.
"""
from fractions import Fraction as Q
import hashlib
import json
import os
from pathlib import Path
import secrets
from statistics import median
import tempfile
import time
from omega_refine_check.syntax import render,substitute,parse
from omega_self_evolve_v2.bridge_lean_filter import verify_receipt
from omega_self_evolve_v2.cycle import evolve_from_receipt
from omega_self_mutate.rules import validate_rule
from omega_selfhost.driver import ROOT,compiler,cc
from omega_platform.sandbox import run
from omega_platform.budget import COMPILER_BUDGET
from .authority import create_key,load_key,public_hex
from .codec import subject
from .toolchain import result


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def nodes(ast):return 1+sum(nodes(x) for x in ast[1:] if isinstance(x,(list,tuple)))


def benchmark(lhs,rhs,variables,*,iterations=2048,repeats=3):
    if type(iterations) is not int or not 128<=iterations<=65536 or type(repeats) is not int or not 3<=repeats<=15 or repeats%2!=1:raise ValueError('Bounded odd repeated native benchmark required')
    timings=[[],[]];checksums=[]
    with tempfile.TemporaryDirectory(prefix='omega-native-profile-') as temporary:
        root=Path(temporary);binaries=[]
        for index,ast in enumerate((lhs,rhs)):
            names={name:('var','input_'+str(i)) for i,name in enumerate(variables)}
            declarations=''.join(f'var input_{i}=(i%97)-{i+48};' for i in range(len(variables)))
            source=root/f'probe{index}.omega'
            source.write_text('funcao principal(){var i=0;var checksum=0;var start=monotonic_ns();enquanto(i<'+str(iterations)+'){'+declarations+'checksum=checksum+('+render(substitute(ast,names))+');i=i+1;}var elapsed=monotonic_ns()-start;print(json([elapsed,text(checksum)]));retornar 0;}')
            c=root/f'probe{index}.c';binary=root/f'probe{index}'
            run([compiler(),source,c],readonly=[source],writable=[root],budget=COMPILER_BUDGET,check=True);cc(c,binary);binaries.append(binary)
        for trial in range(repeats):
            outputs={}
            for index in ((0,1) if trial%2==0 else (1,0)):
                observed=json.loads(run([binaries[index]],budget=COMPILER_BUDGET,check=True).stdout)
                elapsed,checksum=observed
                if type(elapsed) is not int or elapsed<=0:raise ValueError('Nonpositive benchmark timing')
                timings[index].append(elapsed);outputs[index]=checksum
            if outputs[0]!=outputs[1]:raise ValueError('Independent benchmark replay changed output')
            checksums.append(outputs[0])
    return {'format':'omega-native-profile-1','iterations':iterations,'repeats':repeats,'samples_ns':timings,
            'old_ns':int(median(timings[0])),'new_ns':int(median(timings[1])),'checksums':checksums,
            'scope':'Measured on this host, alternating trials; no theorem about hardware throughput'}


def prepare(lhs,receipt,proof_directory,directory,*,authority,policy='native-optimizer-v1',iterations=2048,repeats=3):
    admitted=verify_receipt(receipt,proof_directory,public_key=authority.key.public_key())
    rule=validate_rule(lhs,admitted['statement']['ast'])
    profile=benchmark(rule['lhs'],rule['rhs'],rule['variables'],iterations=iterations,repeats=repeats)
    if profile['new_ns']>=profile['old_ns']:raise ValueError('No measured throughput gain; proposal rejected')
    root=Path(directory).resolve();root.mkdir(parents=True,exist_ok=False)
    source=ROOT/'omega_selfhost/compiler.omega'
    from omega_self_mutate.rules import install_template
    candidate=install_template(source.read_text(),rule).encode();(root/'compiler.omega').write_bytes(candidate)
    from omega_selfhost.proof_protocol import encode
    (root/'tier2-receipt.json').write_bytes(encode(receipt));(root/'profile.json').write_bytes(encode(profile))
    proposal=result('proposal',dict(target='optimizer.omega:'+rule['id'],base_sha256=sha(source),candidate_sha256=sha(root/'compiler.omega'),
       proof_sha256=sha(root/'tier2-receipt.json'),old_ns=profile['old_ns'],new_ns=profile['new_ns'],old_cost=nodes(rule['lhs']),new_cost=nodes(rule['rhs'])))
    # Bind the independently checked equivalence and observed strict gains.
    goals=[parse(f'{proposal["new_ns"]} < {proposal["old_ns"]}'),parse(f'{proposal["new_cost"]} < {proposal["old_cost"]}')]
    permit=authority._issue('incubator.proposal',proposal,policy,goals,root/'permit')
    record={'format':'omega-native-incubation-1','proposal':proposal,'permit':permit,'authority':authority.public,'policy':policy,
            'lhs':rule['lhs'],'proof_directory':str(Path(proof_directory).resolve()),'profile_sha256':sha(root/'profile.json')}
    (root/'proposta_evolucao_001.json').write_bytes(encode(record));return record


def adopt(directory,*,public_key,approval_mode='auto',install=True,commit=False):
    """Noninteractive by default. The caller chooses the trusted mode/key anchor."""
    if approval_mode not in ('auto','manual'):raise ValueError('Unknown supervisor approval mode')
    root=Path(directory).resolve();record=json.loads((root/'proposta_evolucao_001.json').read_text());proposal=record['proposal']
    if record.get('format')!='omega-native-incubation-1' or record['authority']!=public_key.public_bytes_raw().hex():raise ValueError('Proposal issuer not pinned')
    from cryptography.exceptions import InvalidSignature
    try:public_key.verify(bytes.fromhex(record['permit']['signature']),record['permit']['claims'].encode())
    except (ValueError,InvalidSignature) as error:raise PermissionError('Proposal authority signature invalid') from error
    claims=json.loads(record['permit']['claims'])
    if claims.get('subject')!=subject(proposal) or claims.get('policy')!=record['policy'] or claims.get('purpose')!='incubator.proposal' or claims.get('expires',0)<=int(time.time()):raise PermissionError('Unrelated or expired proposal permit')
    source=ROOT/'omega_selfhost/compiler.omega'
    if sha(source)!=proposal['base_sha256'] or sha(root/'compiler.omega')!=proposal['candidate_sha256'] or sha(root/'tier2-receipt.json')!=proposal['proof_sha256']:raise ValueError('Compiler or proposal artifacts changed')
    if sha(root/'profile.json')!=record['profile_sha256']:raise ValueError('Benchmark artifact changed')
    receipt=json.loads((root/'tier2-receipt.json').read_text())
    admitted=verify_receipt(receipt,record['proof_directory'],public_key=public_key)
    rule=validate_rule(record['lhs'],admitted['statement']['ast'])
    from omega_self_mutate.rules import install_template
    if install_template(source.read_text(),rule).encode()!=(root/'compiler.omega').read_bytes():raise ValueError('Candidate is unrelated to the proved mutation')
    # Re-measure just before adoption. Stored claims cannot invent a speed gain.
    profile=json.loads((root/'profile.json').read_text());fresh=benchmark(rule['lhs'],rule['rhs'],rule['variables'],iterations=profile['iterations'],repeats=profile['repeats'])
    if fresh['new_ns']>=fresh['old_ns']:raise ValueError('Measured gain did not survive pre-adoption replay')
    if commit and not install:raise ValueError('A commit requires installation')
    key_path=root/'.approval.seed'
    if not key_path.exists():create_key(key_path)
    key=load_key(key_path);nonce=secrets.token_hex(24)
    request=dict(proposal=proposal,authority=record['authority'],certificate=record['permit'],policy=record['policy'],
                 actor='automatic-supervisor' if approval_mode=='auto' else 'local-operator',key_root=str(root),key_path=key_path.name,nonce=nonce,mode=approval_mode)
    options=dict(readonly=[root])
    if approval_mode=='manual':
        answer=input('[INCUBADORA OMEGA] Incorporar e executar bootstrap? (S/N): ')
        options['input_text']=answer+'\n'
    approved=result('approve',request,**options)
    if not approved.get('approved'):return {'adopted':False,'reason':'operator declined'}
    raw=approved['approval'];key.public_key().verify(bytes.fromhex(approved['signature']),raw.encode());ack=json.loads(raw)
    if ack.get('subject')!=subject(proposal) or ack.get('nonce')!=nonce or ack.get('mode')!=approval_mode or ack.get('expires',0)<=int(time.time()):raise PermissionError('Approval does not authorize this mutation')
    # Exclusive, persistent replay marker. A failed cycle can be reviewed and a
    # fresh proposal prepared; the same approval is never silently retried.
    fd=os.open(root/'.consumed',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    generation=evolve_from_receipt(record['lhs'],receipt,record['proof_directory'],root/'generation',public_key=public_key,
                                  install=install,commit=commit,replace_source=commit,expected_source_sha256=proposal['base_sha256'])
    report={'adopted':bool(install),'bootstrapped':True,'approval_mode':approval_mode,'approval':approved,'profile_replay':fresh,'generation':generation}
    (root/'adoption.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n');return report
