"""Bounded asynchronous elite queue and signed Lean object manifests.

CUDA only supplies data. This host renderer reconstructs the proposition and
compiles it with the trusted Lean toolchain. A .olean has no intrinsic signature;
Ed25519 signs the manifest binding its bytes to the specification and AST.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import re
import tempfile
from omega_refine_check.syntax import tree,evaluate
from omega_refine_check.contracts import verify_contract
from omega_synth_mcts.search import specification
from omega_selfhost.proof_protocol import encode
from omega_platform.sandbox import trusted
from omega_platform.budget import PROOF_BUDGET
from omega_selfhost.proof import lake_binary
from omega_selfhost.axiom_policy import DEFAULT


def digest(value):return hashlib.sha256(encode(value)).hexdigest()


def _compiled(source,expected,directory):
    root=Path(__file__).resolve().parents[1]/'formal/tensor'
    path=directory/'Candidate.lean';path.write_text(source);obj=directory/'Candidate.olean'
    result=trusted([lake_binary(),'env','lean','--root='+str(directory.resolve()),'-o',obj.resolve(),path.resolve()],cwd=root,budget=PROOF_BUDGET,check=True)
    output=result.stdout+result.stderr
    if 'warning:' in output or not obj.is_file() or not obj.stat().st_size:raise ValueError('Lean object compilation was not clean')
    reports={}
    for name,body in re.findall(r"'([^']+)' depends on axioms: \[([^\]]*)\]",output):reports[name]={x.strip() for x in body.split(',') if x.strip()}
    for name in re.findall(r"'([^']+)' does not depend on any axioms",output):reports[name]=set()
    if any(name not in reports or not reports[name]<=DEFAULT for name in expected):raise ValueError('Unauthorized .olean proof dependencies')
    return obj


def _proof_data(spec,ast,bounds):
    proof=verify_contract(spec['variables'],ast,spec['ensures'],requires=spec.get('requires',()))
    if bounds is None:return proof
    if type(bounds) is not dict or set(bounds)!={'inputs','output'} or len(bounds['inputs'])!=len(spec['variables']):raise ValueError('Tier-2 analysis-bound shape mismatch')
    from omega_gpu_mcts.flat import RationalInterval
    for pair in [*bounds['inputs'],bounds['output']]:RationalInterval.from_pair(pair)
    premises=list(spec.get('requires',()))
    for name,pair in zip(spec['variables'],bounds['inputs']):premises.extend([f'{name} >= ({Q(pair[0])})',f'{name} <= ({Q(pair[1])})'])
    lo,hi=map(Q,bounds['output'])
    checked=verify_contract(spec['variables'],ast,f'result >= ({lo}) and result <= ({hi})',requires=premises)
    source=checked['source'].replace('import Omega.Refinement\n','').replace('namespace OmegaRefinement','namespace OmegaTierBounds').replace('end OmegaRefinement','end OmegaTierBounds')
    names={name:name.replace('OmegaRefinement.','OmegaTierBounds.') for name in checked['admission']['theorems']}
    combined=proof['source']+'\n'+source
    admission={'checker':'Lean 4.19.0','source_sha256':hashlib.sha256(combined.encode()).hexdigest(),
               'theorems':proof['admission']['theorems']+list(names.values()),
               'axioms':{**proof['admission']['axioms'],**{names[name]:deps for name,deps in checked['admission']['axioms'].items()}}}
    return {'source':combined,'admission':admission}


def prove_candidate(spec,candidate,directory,*,signing_key,input_bounds=None,output_bounds=None):
    input_names=list(spec['variables'])
    spec=json.loads(encode(spec))
    examples=specification(spec);ast=tree(candidate['ast'])
    if any(evaluate(ast,env)!=target for env,target in examples):raise ValueError('Elite fails independent exact example replay')
    # No mask, reward, supplied C, supplied proof or supplied certificate can
    # replace this independently reconstructed universal proposition.
    bounds=None
    if input_bounds is not None or output_bounds is not None:
        if input_bounds is None or output_bounds is None:raise ValueError('Both analysis input/output bounds are required')
        if len(input_bounds)!=len(input_names):raise ValueError('Tier-2 analysis-bound shape mismatch')
        by_name=dict(zip(input_names,input_bounds))
        bounds={'inputs':[by_name[name] for name in spec['variables']],'output':output_bounds}
    proof=_proof_data(spec,ast,bounds)
    root=Path(directory);root.mkdir(parents=True,exist_ok=False)
    obj=_compiled(proof['source'],proof['admission']['theorems'],root)
    statement={'format':'omega-tier2-statement-1','specification':spec,'ast':ast}
    if bounds is not None:statement['analysis_bounds']=bounds
    manifest={'format':'omega-tier2-object-1','statement':statement,'statement_sha256':digest(statement),
              'lean_source_sha256':hashlib.sha256(proof['source'].encode()).hexdigest(),
              'olean_sha256':hashlib.sha256(obj.read_bytes()).hexdigest(),'admission':proof['admission'],
              'scope':'universal rational contract under stated premises, independent of Tier-1 flags'}
    receipt={'manifest':manifest,'signature':signing_key.sign(encode(manifest)).hex()}
    (root/'certificate.json').write_bytes(encode(receipt))
    return receipt


def verify_receipt(receipt,directory,*,public_key,expected_spec=None):
    if type(receipt) is not dict or set(receipt)!={'manifest','signature'}:raise ValueError('Unknown Tier-2 receipt envelope')
    if len(encode(receipt))>4*1024**2:raise ValueError('Tier-2 receipt byte budget exceeded')
    from cryptography.exceptions import InvalidSignature
    try:public_key.verify(bytes.fromhex(receipt['signature']),encode(receipt['manifest']))
    except (ValueError,TypeError,InvalidSignature) as error:raise PermissionError('Invalid Tier-2 authority signature') from error
    manifest=receipt['manifest'];statement=manifest['statement']
    if manifest.get('format')!='omega-tier2-object-1' or statement.get('format')!='omega-tier2-statement-1' or digest(statement)!=manifest['statement_sha256']:raise ValueError('Changed Tier-2 statement')
    if expected_spec is not None and encode(statement['specification'])!=encode(expected_spec):raise ValueError('Tier-2 receipt belongs to another specification')
    root=Path(directory)
    for name,field in [('Candidate.lean','lean_source_sha256'),('Candidate.olean','olean_sha256')]:
        path=root/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size>64*1024**2 or hashlib.sha256(path.read_bytes()).hexdigest()!=manifest[field]:raise ValueError('Changed Tier-2 proof artifact')
    # Authenticate and re-prove; never import an untrusted arbitrary .olean.
    proof=_proof_data(statement['specification'],tree(statement['ast']),statement.get('analysis_bounds'))
    if (root/'Candidate.lean').read_text()!=proof['source'] or manifest['admission']!=proof['admission']:raise ValueError('Unrelated Tier-2 proof object')
    return {'valid':True,'statement':statement,'statement_sha256':manifest['statement_sha256']}


class LeanBridge:
    def __init__(self,*,signing_key,workers=2,queue_capacity=16):
        if type(workers) is not int or not 1<=workers<=4 or type(queue_capacity) is not int or not workers<=queue_capacity<=256:raise ValueError('Bounded formal worker pool required')
        self.key=signing_key;self.executor=ThreadPoolExecutor(max_workers=workers,thread_name_prefix='omega-tier2')
        self.capacity=queue_capacity;self.closed=False
        self.slots=asyncio.Semaphore(queue_capacity)
    async def consume(self,spec,batch,directory):
        if self.closed:raise RuntimeError('Formal bridge is closed')
        candidates=batch.get('candidates')
        if type(candidates) is not list or len(candidates)>self.capacity:raise ValueError('Formal candidate queue capacity exceeded')
        root=Path(directory);root.mkdir(parents=True,exist_ok=False);loop=asyncio.get_running_loop()
        async def job(index,candidate):
            try:
                async with self.slots:
                    receipt=await loop.run_in_executor(self.executor,lambda:prove_candidate(spec,candidate,root/f'candidate-{index}',signing_key=self.key,
                                                     input_bounds=batch.get('input_bounds'),output_bounds=batch.get('output_bounds')))
                return {'accepted':True,'directory':str(root/f'candidate-{index}'),'receipt':receipt}
            except Exception as error:return {'accepted':False,'reason':str(error)[-4000:]}
        results=await asyncio.gather(*(job(i,c) for i,c in enumerate(candidates)))
        report={'format':'omega-tier2-batch-1','results':results,'accepted':sum(r['accepted'] for r in results)}
        (root/'results.json').write_bytes(encode(report));return report
    async def search_and_consume(self,engine,spec,directory,**search_options):
        batch=await asyncio.to_thread(engine.search,spec,**search_options)
        return await self.consume(spec,batch,directory)
    def close(self):
        self.closed=True;self.executor.shutdown(wait=True,cancel_futures=True)
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
