"""Native CSE proposals and signed, replayed abstraction-library promotion."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
from omega_refine_check.syntax import tree,identifier,render
from omega_selfhost.proof_protocol import encode
from omega_self_evolve_v2.bridge_lean_filter import prove_candidate,verify_receipt


def library_source(entry):
    helper='funcao relu(x){se(x>0){retornar x;}retornar 0;}\n' if 'relu(' in entry['definition'] else ''
    return 'exportar '+entry['name']+';\n'+helper+entry['definition']+'\n'


def native_tool(name,arguments,*,writable=()):
    from omega_selfhost.driver import compiler,cc
    from omega_platform.sandbox import run
    from omega_platform.budget import COMPILER_BUDGET
    package=Path(__file__).resolve().parent
    source=package/name
    if name not in ('sleep_consolidation.omega','abstraction_bank.omega'):raise ValueError('Unknown trusted native autotelic tool')
    with tempfile.TemporaryDirectory(prefix='omega-autotelic-tool-') as temporary:
        # These fixed native JSON tools use the compiler's bootstrapping path.
        # Their dynamically shaped containers exceed the separate bounded
        # Python inference pass. Native tag checks and namespace isolation stay
        # active; proposed abstractions still require independent Tier-2 proofs.
        binary=Path(temporary)/'tool';c=Path(temporary)/'tool.c'
        run([compiler(),source,c],readonly=[source],writable=[temporary],budget=COMPILER_BUDGET,check=True)
        cc(c,binary)
        return run([binary,*map(Path,arguments)],readonly=[p for p in map(Path,arguments) if p.is_file()],writable=list(writable),budget=COMPILER_BUDGET,check=True)


def consolidate(records,*,public_key):
    if type(records) is not list or len(records)>256:raise ValueError('Bounded accepted corpus required')
    corpus=[]
    for record in records:
        verified=verify_receipt(record['receipt'],record['directory'],public_key=public_key)
        from omega_gpu_mcts.flat import FlatBatch
        flat=FlatBatch.create([verified['statement']['ast']],verified['statement']['specification']['variables'])
        if flat.counts[0]>63:raise ValueError('Native consolidation accepts at most 63 nodes per accepted program')
        nodes=[]
        for i in range(flat.counts[0]):
            op=flat.ops[i];value=flat.constants[flat.left[i]] if op==0 else flat.variables[flat.left[i]] if op==1 else ''
            nodes.append({'op':('const','var','+','-','*','/','neg','relu')[op],'left':int(flat.left[i]),'right':int(flat.right[i]),'value':value})
        corpus.append({'id':verified['statement_sha256'],'nodes':nodes})
    with tempfile.TemporaryDirectory(prefix='omega-consolidation-') as temporary:
        root=Path(temporary);path=root/'corpus.json';path.write_bytes(encode(corpus));output=root/'proposals.json'
        native_tool('sleep_consolidation.omega',[path,output],writable=[root])
        proposals=json.loads(output.read_text())
    # Native proposals are data. Revalidate ASTs and free-variable signatures.
    for proposal in proposals:
        from omega_refine_check.syntax import parse
        proposal['ast']=tree(parse(proposal['expression']))
        for name in proposal['parameters']:identifier(name)
    return proposals


class AbstractionBank:
    def __init__(self,directory,*,public_key):
        self.root=Path(directory);self.root.mkdir(parents=True,exist_ok=True);self.public_key=public_key
    def entries(self):
        path=self.root/'bank.json'
        if not path.exists():return []
        if path.is_symlink() or not path.is_file() or path.stat().st_size>16*1024**2:raise ValueError('Bounded regular abstraction bank required')
        entries=json.loads(path.read_text())
        if type(entries) is not list or len(entries)>1024:raise ValueError('Abstraction bank capacity exceeded')
        from cryptography.exceptions import InvalidSignature
        for entry in entries:
            body={k:v for k,v in entry.items() if k!='signature'}
            try:self.public_key.verify(bytes.fromhex(entry['signature']),encode(body))
            except (ValueError,TypeError,InvalidSignature) as error:raise PermissionError('Changed abstraction bank entry') from error
            path=self.root/entry['id']
            verified=verify_receipt(entry['tier2_receipt'],path,public_key=self.public_key,expected_spec=entry['contract'])
            if tree(entry['ast'])!=tree(verified['statement']['ast']):raise ValueError('Unrelated bank abstraction proof')
            expected='funcao '+entry['name']+'('+','.join(entry['parameters'])+'){retornar '+render(tree(entry['ast']))+';}'
            if entry['definition']!=expected:raise ValueError('Changed abstraction definition')
            artifact=path/'abstraction.omega'
            if artifact.is_symlink() or not artifact.is_file() or artifact.read_text()!=library_source(entry):raise ValueError('Changed native abstraction library')
        return entries
    def promote(self,proposal,*,signing_key):
        ast=tree(proposal['ast']);parameters=tuple(identifier(v) for v in proposal['parameters'])
        identity=hashlib.sha256(encode({'ast':ast,'parameters':parameters})).hexdigest()
        name='abstraction_'+identity[:16]
        # A universally valid substitution identity also checks all divisors.
        # Partial subroutines require explicit premises, not guessed safety.
        contract={'variables':{v:'true' for v in parameters},'ensures':'result == '+render(ast),
                  'examples':[{'inputs':{v:'1' for v in parameters},'output':'0'}]}
        from omega_refine_check.syntax import evaluate
        contract['examples'][0]['output']=str(evaluate(ast,{v:__import__('fractions').Fraction(1) for v in parameters}))
        with (self.root/'.bank.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX);existing=self.entries()
            if any(e['id']==identity for e in existing):return next(e for e in existing if e['id']==identity)
            receipt=prove_candidate(contract,{'ast':ast},self.root/identity,signing_key=signing_key)
            body={'id':identity,'name':name,'ast':ast,'parameters':parameters,'contract':contract,
                  'definition':'funcao '+name+'('+','.join(parameters)+'){retornar '+render(ast)+';}',
                  'tier2_receipt':receipt,'structural_gain':proposal.get('structural_gain',0)}
            entry={**body,'signature':signing_key.sign(encode(body)).hex()}
            (self.root/identity/'abstraction.omega').write_text(library_source(entry))
            with tempfile.TemporaryDirectory(prefix='.bank-',dir=self.root) as temporary:
                root=Path(temporary);current=root/'current.json';approved=root/'approved.json';output=root/'next.json'
                current.write_bytes(encode(existing));approved.write_bytes(encode(entry))
                native_tool('abstraction_bank.omega',[current,approved,output],writable=[root])
                result=json.loads(output.read_text())
                if encode(result)!=encode(existing+[entry]):raise ValueError('Native bank transition mismatch')
                os.replace(output,self.root/'bank.json')
            return entry
    def registry(self):
        from omega.generics import Registry
        entries=self.entries()
        return Registry.from_dict({'format':'omega-generics-1','schema_version':'1.0.0','functions':[
            {'name':entry['name'],'parameters':[{'name':name,'shape':[]} for name in entry['parameters']],
             'returns':[],'body':render(tree(entry['ast']))} for entry in entries]})
