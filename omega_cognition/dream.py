"""Sandboxed stochastic proposals with bounded structural/behavioral novelty."""
import hashlib,json,sys,tempfile,math
from pathlib import Path
from omega_agent_sandbox.jail import Jail
from omega_platform.sandbox import ExecutionFailure
from omega_refine_check.syntax import tree,render,evaluate
from .problem import flat

ROOT=Path(__file__).resolve().parents[1]


def propose(problem,*,seed=0,iterations=256,temperature=2.0,guide='heuristic',jail=None):
    if type(seed) is not int or not 0<=seed<2**63 or type(iterations) is not int or not 1<=iterations<=100000:raise ValueError('Proposal limits')
    if type(temperature) not in (int,float) or not math.isfinite(temperature) or not 1<=temperature<=20 or guide not in ('heuristic','neural'):raise ValueError('Proposal temperature/guide')
    jail=jail or Jail(memory_bytes=8*1024**3 if guide=='neural' else 1024**3)
    payload={'spec':problem['search_spec'],'guide':guide,'temperature':temperature,
             'limits':{'seed':seed,'iterations':iterations,'seconds':min(30,jail.wall_seconds),'max_nodes':15,'max_depth':8}}
    package=ROOT/'omega_cognition'
    with tempfile.TemporaryDirectory(prefix='omega-dream-') as tmp:
        p=Path(tmp)/'proposal.json';p.write_text(json.dumps(payload))
        mounts=[ROOT/name for name in ('omega_cognition','omega_synth_mcts','omega_refine_check','omega','omega_selfhost','omega_platform')]
        mounts+=[Path(sys.base_prefix)/'lib',p]
        argv=[sys.executable,'-E','-S','-B',package/'dream_worker.py',p]
        if guide=='neural':
            # Optional installed neural stack, read-only, still no home/network.
            import site
            paths=[v for v in site.getsitepackages() if Path(v).is_dir()]
            mounts.extend(Path(v) for v in paths)
            payload['python_paths']=paths;p.write_text(json.dumps(payload))
        outcome=jail.execute(argv,readonly=mounts,threads=guide=='neural')
    if not outcome.ok:return {'status':'execution_failed','termination':outcome.termination,'returncode':outcome.returncode,'sandboxed':outcome.sandboxed}
    value=json.loads(outcome.stdout)
    if value.get('verified') is not False:raise ValueError('Proposal worker cannot admit candidates')
    candidate=value.get('candidate')
    if candidate is None:return {'status':'exhausted','sandboxed':True}
    candidate=tree(candidate);flat(candidate,list(problem['grid']))
    return {'status':'proposed','candidate':candidate,'source':render(candidate),'sandboxed':True,
            'evaluations':value['evaluations'],'temperature':temperature,'guide':guide,'formal_admission':False}


def novelty(candidate,problem):
    # Behavioral fingerprints on training probes are a heuristic, not proof of
    # semantic novelty, and never count as independent validation observations.
    values=[]
    for row in problem['training']:
        from fractions import Fraction
        try:values.append(str(evaluate(candidate,{k:Fraction(v) for k,v in row['inputs'].items()})))
        except (ZeroDivisionError,ValueError,OverflowError):values.append('partial')
    raw=json.dumps(values,separators=(',',':')).encode()
    return hashlib.sha256(raw).hexdigest()
