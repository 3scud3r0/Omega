"""Frozen hypotheses, independent validation draws and adversarial counterexamples."""
from fractions import Fraction
import hashlib,json,random,secrets,time
from decimal import Decimal
from .native import call
from .problem import flat
from .statistics import confidence


def boundaries(problem):
    names=list(problem['grid']);mid={k:Fraction((lo+hi)//2,d) for k,(lo,hi,d) in problem['grid'].items()}
    rows=[mid]
    for name,(lo,hi,d) in problem['grid'].items():
        values={lo,hi,(lo+hi)//2,max(lo,min(hi,0)),min(hi,lo+1),max(lo,hi-1)}
        for n in sorted(values):rows.append({**mid,name:Fraction(n,d)})
    for observed in problem['training']:
        origin={k:Fraction(v) for k,v in observed['inputs'].items()}
        rows.append(origin)
        for name,(lo,hi,d) in problem['grid'].items():
            for delta in [-1,1]:
                q=origin[name]+Fraction(delta,d)
                if Fraction(lo,d)<=q<=Fraction(hi,d):rows.append({**origin,name:q})
    seen=set();out=[]
    for row in rows:
        encoded=tuple(str(row[n]) for n in names)
        if encoded not in seen:seen.add(encoded);out.append(list(encoded))
    return out


def evaluate(candidate,problem,*,trials=100000,alpha='0.05',epsilon='0.00001',seed=None,jail=None,wall_seconds=300):
    if type(trials) is not int or not 1<=trials<=2_000_000:raise ValueError('IID trial budget')
    if type(wall_seconds) not in (int,float) or not 1<=wall_seconds<=3600:raise ValueError('Debate watchdog')
    names=list(problem['grid']);ast=flat(candidate,names);oracle=flat(problem['reference'],names)
    subject=hashlib.sha256(json.dumps(ast,separators=(',',':')).encode()).hexdigest()
    # The default validation seed is fresh, not derived from the proposal seed.
    seed=secrets.randbits(128) if seed is None else seed
    if type(seed) is not int or not 0<=seed<2**128:raise ValueError('Validation seed')
    rng=random.Random(seed);started=time.monotonic();counts={'adversarial':0,'iid':0};failures={'adversarial':0,'iid':0};counterexample=None;transcript=hashlib.sha256();checkpoints=[]
    def batch(rows,critic):
        nonlocal counterexample
        if time.monotonic()-started>wall_seconds:raise TimeoutError('Total debate wall budget')
        result=call('batch',{'candidate':ast,'oracle':oracle,'width':len(names),'rows':rows},jail=jail)
        if result['tested']!=len(rows) or not 0<=result['failures']<=len(rows):raise ValueError('Native debate result integrity')
        if result['oracle_errors']:raise ValueError('Host oracle is undefined in the declared distribution')
        transcript.update(json.dumps({'critic':critic,'rows':rows,'result':result},sort_keys=True,separators=(',',':')).encode())
        counts[critic]+=len(rows);failures[critic]+=result['failures']
        if result['failures'] and counterexample is None:counterexample={'critic':critic,**result['counterexample']}
        return result['failures']==0
    rows=boundaries(problem)
    if batch(rows,'adversarial'):
        while counts['iid']<trials:
            n=min(1024,trials-counts['iid']);rows=[]
            for _ in range(n):rows.append([str(Fraction(rng.randint(lo,hi),d)) for lo,hi,d in problem['grid'].values()])
            if not batch(rows,'iid'):break
            checkpoints.append({'tested':counts['iid'],'failures':failures['iid']})
    assessed=confidence(counts['iid'],failures['iid'],alpha=alpha,epsilon=epsilon)
    accepted=not any(failures.values()) and counts['iid']==trials and assessed['accepted']
    return {'format':'omega-empirical-evidence-1','candidate_sha256':subject,'status':'empirically_stable' if accepted else 'falsified' if any(failures.values()) else 'insufficient_evidence',
            'accepted':accepted,'counts':counts,'failures':failures,'confidence':assessed,'validation_seed':seed,
            'distribution':{'kind':'uniform_independent_grid','variables':problem['grid'],'generator':'Python MT19937; IID assumption is explicit'},
            'counterexample':counterexample,'transcript_sha256':transcript.hexdigest(),'convergence_checkpoints':checkpoints[-8:],
            'formal_admission':False,'seconds':time.monotonic()-started}
