"""Dream→falsification→Lean artifacts. Proposal never grants promotion authority."""
from dataclasses import dataclass,asdict
from decimal import Decimal,localcontext,ROUND_FLOOR
import hashlib,json,math,time
from pathlib import Path
from .problem import normalize,flat
from .statistics import probability,required_trials
from .native import call
from .dream import propose,novelty
from .debate import evaluate
from . import bridge
from omega_agent_sandbox.jail import Jail
from omega_refine_check.syntax import render,tree

MODES=('strict','empirical','dream','creative','bicameral')

@dataclass(frozen=True)
class Options:
    mode:str='strict'
    cases:int|None=None
    alpha:str='0.05'
    epsilon:str='0.00001'
    cycles:int=1
    proposals:int=4
    iterations:int=256
    seed:int=0
    temperature:float=2.0
    guide:str='heuristic'
    max_total_trials:int=2_000_000
    wall_seconds:int=300
    bft:bool=False
    native:bool=True
    zk_prover:str|None=None
    zk_verifier:str|None=None
    require_seal:bool=False
    proposal_source:str='mixed'

    def __post_init__(self):
        if self.mode not in MODES or self.guide not in ('heuristic','neural'):raise ValueError('Cognitive mode/guide')
        for name,lo,hi in [('cycles',1,16),('proposals',1,32),('iterations',1,100000),('seed',0,2**63-1),('max_total_trials',1,2_000_000),('wall_seconds',1,3600)]:
            if type(getattr(self,name)) is not int or not lo<=getattr(self,name)<=hi:raise ValueError('Cognitive quota: '+name)
        if self.cases is not None and (type(self.cases) is not int or not 1<=self.cases<=2_000_000):raise ValueError('Cases budget')
        probability(self.alpha);probability(self.epsilon)
        if type(self.temperature) not in (int,float) or not math.isfinite(self.temperature) or not 1<=self.temperature<=20:raise ValueError('Temperature in [1,20]')
        if type(self.bft) is not bool or type(self.native) is not bool or bool(self.zk_prover)!=bool(self.zk_verifier):raise ValueError('Explicit BFT/native and paired ZK tools required')
        if self.proposal_source not in ('search','seeds','mixed'):raise ValueError('Proposal source')
        if type(self.require_seal) is not bool:raise ValueError('Explicit seal policy required')
        if self.require_seal and (self.mode not in ('strict','bicameral') or not self.native or not self.zk_prover):
            raise ValueError('Required crystallization needs strict/bicameral, native emission and both ZK tools')


def dump(path,value):path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def run(spec,directory,*,options=None,jail=None):
    config=options or Options();mode='dream' if config.mode=='creative' else config.mode
    problem=normalize(spec);root=Path(directory).resolve()
    if root.exists():raise FileExistsError(root)
    root.mkdir(parents=True,mode=0o700)
    jail=jail or Jail(memory_bytes=8*1024**3 if config.guide=='neural' else 1024**3)
    call('jail',asdict(jail))
    dump(root/'problem.json',spec);dump(root/'configuration.json',asdict(config))
    report={'format':'omega-bicameral-report-1','mode':mode,'problem_sha256':digest(spec),'candidates':[],
            'extensions':[{'syntax':e,'status':'quarantined_unsupported_semantics','executed':False} for e in problem['extensions']],
            'events':[],'kernel_activated':False,'activation_requires_independent_approval':True,'zk_verified':False,'completed_cycles':0}
    previous='0'*64;seen=set();used=0;reserved=0;accounting_complete=True;started=time.monotonic()
    with localcontext() as precision:
        precision.prec=70;precision.rounding=ROUND_FLOOR
        per_alpha=str(Decimal(config.alpha)/(config.proposals*config.cycles))
    trials=config.cases if config.cases is not None else max(100000,required_trials(alpha=per_alpha,epsilon=config.epsilon))
    report['validation_policy']={'alpha_family':config.alpha,'alpha_per_candidate':per_alpha,'planned_iid_trials':trials,
                                  'multiple_comparisons':config.proposals*config.cycles,'max_total_trials':config.max_total_trials}
    def event(subject,phase,what):
        nonlocal previous
        state=call('transition',{'mode':mode,'phase':phase,'event':what},jail=jail)
        record={'candidate_sha256':subject,'event':what,'state':state,'previous_sha256':previous}
        previous=digest(record);record['sha256']=previous;report['events'].append(record)
        with (root/'audit.jsonl').open('a') as out:out.write(json.dumps(record,sort_keys=True)+'\n')
        return state['phase']
    try:
        for cycle in range(config.cycles):
            if time.monotonic()-started>=config.wall_seconds:report['stop_reason']='wall_budget';break
            seeds=[];proposals=[]
            for c in problem['candidates']:
                if mode in ('dream','bicameral'):
                    seeds.append((('+',c,('const','0')),{'origin':'sandbox_checked_ast_mutation','mutation':'add-neutral-element','verified':False}))
                else:proposals.append((c,{'origin':'caller_seed','verified':False}))
            if mode in ('dream','bicameral') and config.proposal_source!='seeds':
                for i in range(config.proposals):
                    if time.monotonic()-started>=config.wall_seconds:break
                    result=propose(problem,seed=(config.seed+cycle*config.proposals+i)%(2**63),iterations=config.iterations,
                                   temperature=config.temperature,guide=config.guide,jail=jail)
                    if result['status']=='proposed':proposals.append((result['candidate'],{k:v for k,v in result.items() if k!='candidate'}))
                    else:report.setdefault('proposal_failures',[]).append(result)
            if mode in ('dream','bicameral') and config.proposal_source!='search':proposals.extend(seeds)
            if mode in ('strict','empirical') and not proposals:raise ValueError('This mode requires explicit candidate hypotheses')
            # Count unique hypotheses, not duplicated search outputs. Search
            # proposals come first so caller seeds cannot starve the generator.
            selected=[];identities=set(seen)
            for candidate,origin in proposals:
                identity=digest(flat(candidate,list(problem['grid'])))
                if identity not in identities:selected.append((candidate,origin));identities.add(identity)
            accepted_this_cycle=False
            for candidate,origin in selected[:config.proposals]:
                if time.monotonic()-started>=config.wall_seconds:report['stop_reason']='wall_budget';break
                signature=novelty(candidate,problem)
                identity=digest(flat(candidate,list(problem['grid'])))
                if identity in seen:continue
                seen.add(identity)
                folder=root/f'candidate-{len(report["candidates"]):03}';folder.mkdir()
                row={'sha256':identity,'expression':render(candidate),'origin':origin,'novelty_signature':signature,'formal_admission':False,'kernel_activated':False}
                dump(folder/'candidate.json',row);report['candidates'].append(row)
                phase=event(identity,'new','propose')
                if mode=='dream':row['status']='quarantined';continue
                if mode!='strict':
                    phase=event(identity,phase,'debate')
                    if reserved+trials>config.max_total_trials:row['status']='resource_exhausted';report['stop_reason']='trial_budget';break
                    # Never refund a failed/aborted experiment: it may already
                    # have consumed draws before its subprocess failed.
                    reserved+=trials
                    try:
                        evidence=evaluate(candidate,problem,trials=trials,alpha=per_alpha,epsilon=config.epsilon,jail=jail,
                                          wall_seconds=max(1,config.wall_seconds-(time.monotonic()-started)))
                    except (ValueError,TimeoutError,RuntimeError) as error:
                        accounting_complete=False
                        row['status']='validation_failed';row['reason']=str(error)[-2000:];continue
                    used+=evidence['counts']['iid'];row['empirical']=evidence;dump(folder/'empirical.json',evidence)
                    phase=event(identity,phase,'stable' if evidence['accepted'] else 'counterexample' if evidence['status']=='falsified' else 'insufficient')
                    row['status']=evidence['status']
                    if not evidence['accepted']:continue
                    if config.bft:
                        # Explicit local four-process test network, not external
                        # consensus authority or an Internet publication.
                        from omega_sovereign.bft import experiment
                        payload={'kind':'empirically_stable','candidate_sha256':identity,'evidence_sha256':digest(evidence),'formal_admission':False}
                        dump(folder/'ledger-object.json',payload)
                        try:row['bft']=experiment(folder/'bft',value=digest(payload))
                        except (ValueError,RuntimeError,OSError) as error:
                            row['ledger_error']=str(error)[-2000:];row['status']='empirical_ledger_failed'
                            event(identity,phase,'fail_empirical_ledger');continue
                        row['bft']['scope']='local fixed-membership test cluster; not production network authority'
                    if mode=='empirical':accepted_this_cycle=True;continue
                    phase=event(identity,phase,'crystallize')
                try:proof=bridge.prove(candidate,problem,folder/'formal')
                except (ValueError,RuntimeError) as error:
                    event(identity,phase,'unproved');row['status']='formal_unproved';row['reason']=str(error)[-2000:];continue
                row['formal_admission']=True;row['formal']=proof;dump(folder/'formal/receipt.json',proof)
                phase=event(identity,phase,'proved');row['status']='formal_verified'
                if config.native:
                    try:
                        row['native']=bridge.emit_rv64(candidate,problem,folder/'native');phase=event(identity,phase,'emit');row['status']='native_emitted'
                    except (ValueError,RuntimeError,OSError) as error:
                        row['native_error']=str(error)[-1000:];row['status']='native_failed';phase=event(identity,phase,'fail_emit')
                if config.zk_prover and phase=='native_emitted':
                    try:
                        raw,receipt=bridge.seal(candidate,problem,prover=config.zk_prover,verifier=config.zk_verifier)
                        (folder/'receipt.stark').write_bytes(raw);dump(folder/'zk.json',receipt);row['zk']=receipt
                        phase=event(identity,phase,'seal');row['status']='zk_verified';report['zk_verified']=True
                    except (ValueError,RuntimeError,OSError) as error:
                        row['zk_error']=str(error)[-2000:];row['status']='zk_failed';phase=event(identity,phase,'fail_seal')
                if phase=='zk_verified':
                    from .crystallization import publish
                    dump(folder/'hypothesis.json',{'format':'omega-cognitive-hypothesis-1','problem':spec,'candidate':render(candidate),'ast':tree(candidate)})
                    try:
                        row['crystallization']=publish(folder,empirical=mode!='strict')
                        phase=event(identity,phase,'publish');row['status']='crystallized'
                    except (ValueError,RuntimeError,OSError) as error:
                        row['artifact_error']=str(error)[-2000:];row['status']='artifact_failed';phase=event(identity,phase,'fail_publish')
                    if row['status']=='crystallized' and config.bft:
                        try:
                            from omega_sovereign.bft import experiment
                            payload={'kind':'crystallized','candidate_sha256':identity,
                                     'manifest_sha256':row['crystallization']['sha256'],'kernel_activated':False}
                            dump(folder/'final-ledger-object.json',payload)
                            row['final_bft']=experiment(folder/'bft-final',value=digest(payload))
                        except (ValueError,RuntimeError,OSError) as error:
                            row['ledger_error']=str(error)[-2000:];row['status']='ledger_failed';phase=event(identity,phase,'fail_ledger')
                row['promotion']='pending_independent_approval'
                target='crystallized' if config.zk_prover else 'native_emitted' if config.native else 'formal_verified'
                accepted_this_cycle=row['status']==target
                if mode=='bicameral' and accepted_this_cycle:break
            report['completed_cycles']+=1
            if mode=='bicameral' and accepted_this_cycle:
                report['stop_reason']='crystallization_ready' if config.zk_prover else 'formal_artifact_ready';break
        report['iid_trials_executed']=used
        report['iid_accounting_complete']=accounting_complete
        report['iid_trial_budget_reserved']=reserved
        report.setdefault('stop_reason','cycle_budget')
        report['status']='formal_verified' if any(c['formal_admission'] for c in report['candidates']) else 'empirically_stable' if any(c.get('empirical',{}).get('accepted') for c in report['candidates']) else 'quarantined' if mode=='dream' else 'no_admitted_hypothesis'
        report['crystallization_complete']=any(c.get('status')=='crystallized' for c in report['candidates'])
        if report['crystallization_complete']:report['status']='crystallized'
        target='quarantined' if mode=='dream' else 'empirically_stable' if mode=='empirical' else 'crystallized' if config.zk_prover else 'native_emitted' if config.native else 'formal_verified'
        report['completion_target']=target
        report['configured_stages_complete']=any(c.get('status')==target for c in report['candidates'])
        report['pending_stages']=[label for label,key in [('lean','formal_admission'),('rv64','native'),('stark','zk'),('artifact','crystallization')] if not any(c.get(key) for c in report['candidates'])]
        if config.bft:
            ledger='bft' if mode=='empirical' else 'final_bft'
            if not any(c.get(ledger,{}).get('converged') for c in report['candidates']):report['pending_stages'].append('ledger')
        return report
    finally:
        report['artifact_sha256']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and p.name!='report.json'}
        dump(root/'report.json',report)
