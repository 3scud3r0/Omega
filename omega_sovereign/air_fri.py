"""Experimental transparent AIR/FRI proof for a bounded arithmetic machine.

Machine: x[i+1] = x[i]**2 + c over the Goldilocks field. A transition quotient
and two boundary quotients are randomly combined, then low-degree tested with
Merkle-authenticated FRI queries. Verification does not re-execute the trace.

NOT zero knowledge: openings reveal witness evaluations. NOT an audited STARK
or a proof system for arbitrary Omega code. The 64-bit field limits algebraic
soundness; no 128-bit security claim is made. Use for research and tests only.
"""
from hashlib import sha3_256
import json

P=2**64-2**32+1
GENERATOR=7
BLOWUP=8
MAX_STEPS=256
MAX_PROOF_BYTES=2*1024**2


def h(data):return sha3_256(data).digest()
def inv(x):
    if x%P==0:raise ValueError('Zero field divisor')
    return pow(x,P-2,P)
def field(x):return type(x) is int and 0<=x<P
def pack(x):return x.to_bytes(8,'little')
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':')).encode()
def challenge(transcript,label):return int.from_bytes(h(label+transcript),'little')%P


def fft(values, root):
    n=len(values)
    if n==1:return values[:]
    even=fft(values[::2],root*root%P);odd=fft(values[1::2],root*root%P)
    result=[0]*n;w=1
    for i in range(n//2):
        v=w*odd[i]%P
        result[i]=(even[i]+v)%P;result[i+n//2]=(even[i]-v)%P
        w=w*root%P
    return result


def lde(trace):
    t=len(trace);n=t*BLOWUP
    coefficients=fft(trace,inv(pow(GENERATOR,(P-1)//t,P)))
    factor=inv(t);coset=1
    for i in range(t):
        coefficients[i]=coefficients[i]*factor*coset%P
        coset=coset*3%P
    return fft(coefficients+[0]*(n-t),pow(GENERATOR,(P-1)//n,P))


def tree(values):
    layers=[[h(b'leaf'+pack(v)) for v in values]]
    while len(layers[-1])>1:
        previous=layers[-1]
        layers.append([h(b'node'+previous[i]+previous[i+1]) for i in range(0,len(previous),2)])
    return layers


def opening(values,layers,index):
    siblings=[];j=index
    for layer in layers[:-1]:siblings.append(layer[j^1].hex());j//=2
    return {'value':values[index],'path':siblings}


def check_open(root,index,size,proof):
    if type(proof) is not dict or set(proof)!= {'value','path'} or not field(proof['value']):return False
    path=proof['path']
    if type(path) is not list or len(path)!=size.bit_length()-1:return False
    result=h(b'leaf'+pack(proof['value']))
    for sibling in path:
        if type(sibling) is not str or len(sibling)!=64:return False
        sibling=bytes.fromhex(sibling)
        result=h(b'node'+(sibling+result if index&1 else result+sibling));index//=2
    return result.hex()==root


def statement(start,c,steps,end):
    if not all(field(v) for v in (start,c,end)):raise ValueError('Noncanonical field element')
    if type(steps) is not int or not 8<=steps<=MAX_STEPS or steps&(steps-1):raise ValueError('Steps must be a power of two in [8,256]')
    return {'version':'omega-air-fri-research-1','start':start,'c':c,'steps':steps,'end':end}


def composition(x,a,shifted,s,alpha):
    last=pow(GENERATOR,(P-1)//s['steps']*(s['steps']-1),P)
    transition=(shifted-a*a-s['c'])*((x-last)*inv(pow(x,s['steps'],P)-1)%P)%P
    first=(a-s['start'])*inv(x-1)%P
    final=(a-s['end'])*inv(x-last)%P
    return (transition+alpha*first+alpha*alpha*final)%P


def indices(transcript,n,queries):
    return [int.from_bytes(h(b'query'+transcript+i.to_bytes(4,'little')),'little')%n for i in range(queries)]


def prove(start,c,steps,*,queries=32,trace=None):
    statement(start,c,steps,0)
    if type(queries) is not int or not 16<=queries<=64:raise ValueError('Query budget [16,64]')
    if trace is None:
        trace=[start]
        for _ in range(steps-1):trace.append((trace[-1]**2+c)%P)
    if len(trace)!=steps or not all(field(v) for v in trace):raise ValueError('Trace shape')
    if trace[0]!=start or any(trace[i+1]!=(trace[i]**2+c)%P for i in range(steps-1)):
        raise ValueError('Unsatisfied execution trace')
    s=statement(start,c,steps,trace[-1]);n=steps*BLOWUP
    a=lde(trace);at=tree(a);aroot=at[-1][0].hex()
    transcript=canonical(s)+bytes.fromhex(aroot)
    alpha=challenge(transcript,b'composition')
    omega=pow(GENERATOR,(P-1)//n,P);x=3;q=[]
    for i in range(n):
        q.append(composition(x,a[i],a[(i+BLOWUP)%n],s,alpha));x=x*omega%P
    qt=tree(q);qroot=qt[-1][0].hex();transcript+=bytes.fromhex(qroot)
    beta=challenge(transcript,b'batch')
    values=[(v+beta*w)%P for v,w in zip(a,q)]
    layers=[];trees=[];roots=[];domain=3;generator=omega;degree=steps
    while True:
        layer=tree(values);layers.append(values);trees.append(layer);roots.append(layer[-1][0].hex())
        transcript+=bytes.fromhex(roots[-1])
        if degree==1:break
        fold=challenge(transcript,b'fold');half=len(values)//2;x=domain;new=[]
        for i in range(half):
            u,v=values[i],values[i+half]
            new.append(((u+v)*inv(2)+fold*(u-v)*inv(2*x))%P);x=x*generator%P
        values=new;domain=domain*domain%P;generator=generator*generator%P;degree//=2
    if len(set(values))!=1:raise ValueError('FRI terminal polynomial is not constant')
    records=[]
    for index in indices(transcript,n,queries):
        folds=[];j=index
        for vals,ts in zip(layers[:-1],trees[:-1]):
            half=len(vals)//2;base=j%half
            folds.append([opening(vals,ts,base),opening(vals,ts,base+half)]);j=base
        records.append({'a':opening(a,at,index),'next':opening(a,at,(index+BLOWUP)%n),
                        'q':opening(q,qt,index),'folds':folds})
    proof={'statement':s,'a_root':aroot,'q_root':qroot,'fri_roots':roots,
           'final':values,'queries':queries,'openings':records}
    if len(canonical(proof))>MAX_PROOF_BYTES:raise ValueError('Proof byte budget')
    return proof


def verify(proof,expected,*,min_queries=32):
    """Expected public statement is caller supplied, never taken on trust.

    All input bounds are checked before FFTs/large allocations (the verifier
    uses neither). Invalid/ambiguous/unbound proofs fail closed.
    """
    try:
        if type(min_queries) is not int or not 16<=min_queries<=64:return False
        if type(proof) is not dict or len(canonical(proof))>MAX_PROOF_BYTES:return False
        if set(proof)!={'statement','a_root','q_root','fri_roots','final','queries','openings'}:return False
        s=proof['statement']
        if s!=expected or s!=statement(s['start'],s['c'],s['steps'],s['end']):return False
        steps=s['steps'];n=steps*BLOWUP;count=proof['queries']
        if type(count) is not int or not min_queries<=count<=64:return False
        roots=proof['fri_roots'];final=proof['final'];records=proof['openings']
        if type(roots) is not list or len(roots)!=steps.bit_length():return False
        if any(type(r) is not str or len(r)!=64 for r in [proof['a_root'],proof['q_root'],*roots]):return False
        if type(final) is not list or len(final)!=BLOWUP or not all(field(v) for v in final) or len(set(final))!=1:return False
        if tree(final)[-1][0].hex()!=roots[-1]:return False
        if type(records) is not list or len(records)!=count:return False
        transcript=canonical(s)+bytes.fromhex(proof['a_root'])
        alpha=challenge(transcript,b'composition');transcript+=bytes.fromhex(proof['q_root'])
        beta=challenge(transcript,b'batch');fold_challenges=[]
        for root in roots:
            transcript+=bytes.fromhex(root);fold_challenges.append(challenge(transcript,b'fold'))
        omega=pow(GENERATOR,(P-1)//n,P)
        for index,record in zip(indices(transcript,n,count),records):
            if set(record)!={'a','next','q','folds'} or len(record['folds'])!=len(roots)-1:return False
            if not check_open(proof['a_root'],index,n,record['a']):return False
            if not check_open(proof['a_root'],(index+BLOWUP)%n,n,record['next']):return False
            if not check_open(proof['q_root'],index,n,record['q']):return False
            x=3*pow(omega,index,P)%P
            if composition(x,record['a']['value'],record['next']['value'],s,alpha)!=record['q']['value']:return False
            want=(record['a']['value']+beta*record['q']['value'])%P
            size=n;j=index;domain=3;generator=omega
            for level,pair in enumerate(record['folds']):
                if type(pair) is not list or len(pair)!=2:return False
                base=j%(size//2);u,v=pair
                if not check_open(roots[level],base,size,u) or not check_open(roots[level],base+size//2,size,v):return False
                if (u if j<size//2 else v)['value']!=want:return False
                x=domain*pow(generator,base,P)%P
                want=((u['value']+v['value'])*inv(2)+fold_challenges[level]*(u['value']-v['value'])*inv(2*x))%P
                j=base;size//=2;domain=domain*domain%P;generator=generator*generator%P
            if want!=final[j]:return False
        return True
    except (ValueError,KeyError,TypeError,IndexError,OverflowError,RecursionError):return False
