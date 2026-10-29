"""Reconstruct Lean proofs for the actual endpoints returned by native math.

Python renders witnesses; all endpoints originate in the native .omega program.
No floating point calculation or supplied Lean source enters the proof.
"""
from fractions import Fraction as Q
from math import factorial
from pathlib import Path
import hashlib
from omega.transcendental import real as R
from omega_self_evolve_v2.bridge_lean_filter import _compiled
from .toolchain import result


def rounded(lo,hi,scale):return Q((lo*scale).__floor__(),scale),Q((hi*scale).__ceil__(),scale)
def multiply(a,b):
    p=[x*y for x in a for y in b];return min(p),max(p)
def enclosure(function,x,pair):return f'{R(pair[0])} ≤ Real.{function} {R(x)} ∧ Real.{function} {R(x)} ≤ {R(pair[1])}'
def numeric():return '(by norm_num)'


def exp_proof(x,bits,observed):
    if not x:return ['  norm_num']
    work_bits=bits+2*abs(x).__ceil__()+24;scale=1<<work_bits;u=abs(x);shifts=0
    while u>1:u/=2;shifts+=1
    n=work_bits+8;s=sum((u**i/factorial(i) for i in range(n)),Q(0));error=Q(n+1,factorial(n)*n)
    pair=rounded(s-error,s+error,scale)
    lines=[f'  have e0 : {enclosure("exp",u,pair)} := by',f'    have h := OmegaReal.taylor_uniform {R(u)} {n} (by norm_num) (by norm_num [abs_of_nonneg])',
           '    norm_num [Finset.sum_range_succ, Nat.factorial] at h', '    have a := (abs_le.mp h).1','    have b := (abs_le.mp h).2', '    constructor <;> linarith only [a,b]']
    for i in range(shifts):
        new=rounded(pair[0]**2,pair[1]**2,scale)
        lines.extend([f'  have e{i+1} : {enclosure("exp",2*u,new)} := by',f'    rw [show {R(2*u)} = {R(u)} + {R(u)} by norm_num]',
                      f'    exact OmegaReal.exp_double {R(u)} {R(pair[0])} {R(pair[1])} {R(new[0])} {R(new[1])} (by norm_num) e{i} (by norm_num) (by norm_num)'])
        pair=new;u*=2
    if x<0:
        lines.extend([f'  rw [show {R(x)} = -{R(-x)} by norm_num, Real.exp_neg]',
                      f'  have invh := OmegaReal.inv_bounds (Real.exp {R(-x)}) {R(pair[0])} {R(pair[1])} (by norm_num) e{shifts}',
                      '  constructor <;> norm_num [one_div] at * <;> linarith [invh.1,invh.2]'])
    else:lines.append(f'  exact e{shifts}')
    return lines


def log_proof(x,bits,observed):
    if x==1:return ['  norm_num']
    m=x;k=0
    while m>2:m/=2;k+=1
    while m<1:m*=2;k-=1
    n=bits+16;lines=[]
    for name,t in [('unit',m),('two',Q(2))]:
        if t==1:
            lines.append(f'  have {name} : {enclosure("log",t,(Q(0),Q(0)))} := by norm_num')
            continue
        z=(t-1)/(t+1);s=sum((2*z**i/i for i in range(1,n+1) if i%2),Q(0));e=2*abs(z**(n+1))/(1-abs(z))
        lines.extend([f'  have {name} : {enclosure("log",t,(s-e,s+e))} := by',f'    have h := OmegaNative.log_ratio_enclosure {R(z)} (by norm_num [abs_of_nonneg]) {n}',
                      '    norm_num [abs_of_nonneg, Finset.sum_range_succ] at h', '    have a := (abs_le.mp h).1','    have b := (abs_le.mp h).2', '    constructor <;> linarith only [a,b]'])
    lines.extend([f'  have positive : (0 : ℝ) < {R(m)} := by norm_num',
                  f'  have shift : Real.log {R(x)} = Real.log {R(m)} + ({k} : ℝ)*Real.log 2 := by',
                  f'    calc',f'      Real.log {R(x)} = Real.log ({R(m)} * (2 : ℝ)^({k} : ℤ))  := by norm_num',f'      _ = Real.log {R(m)} + Real.log ((2 : ℝ)^({k} : ℤ)) := Real.log_mul (ne_of_gt positive) (by positivity)',f'      _ = Real.log {R(m)} + ({k} : ℝ)*Real.log 2 := by rw [Real.log_zpow]; norm_num',
                  '  rw [shift]','  constructor <;> linarith [unit.1,unit.2,two.1,two.2]'])
    return lines


def trig_proof(x,bits,observed):
    if x==0:return ['  norm_num']
    shifts=bits+14;scale=1<<(bits+2*shifts+32);u=x/(1<<shifts);err=abs(u)**4*Q(5,96)
    s=rounded(u-u**3/6-err,u-u**3/6+err,scale);c=rounded(1-u*u/2-err,1-u*u/2+err,scale)
    lines=[]
    for function,pair in [('sin',s),('cos',c)]:
        lines.extend([f'  have {function}0 : {enclosure(function,u,pair)} := by',f'    have h := OmegaNative.small_{function} {R(u)} (by norm_num [abs_of_nonneg,abs_of_nonpos])',
                      '    norm_num [abs_of_nonneg,abs_of_nonpos] at h','    constructor <;> linarith [h.1,h.2]'])
    for i in range(shifts):
        p=multiply(s,c);ss=multiply(s,s);cc=multiply(c,c)
        for name,a,b,pair,ha,hb,fa,fb in [('p',s,c,p,f'sin{i}',f'cos{i}','sin','cos'),('ss',s,s,ss,f'sin{i}',f'sin{i}','sin','sin'),('cc',c,c,cc,f'cos{i}',f'cos{i}','cos','cos')]:
            lines.append(f'  have {name}{i} := OmegaReal.mul_bounds (Real.{fa} {R(u)}) (Real.{fb} {R(u)}) '+ ' '.join(R(v) for v in (*a,*b,*pair))+f' {ha} {hb} '+' '.join([numeric()]*8))
        ns=rounded(max(Q(-1),2*p[0]),min(Q(1),2*p[1]),scale)
        nc=rounded(max(Q(-1),cc[0]-ss[1]),min(Q(1),cc[1]-ss[0]),scale)
        for function,pair in [('sin',ns),('cos',nc)]:
            fact=f'p{i}.1,p{i}.2' if function=='sin' else f'ss{i}.1,ss{i}.2,cc{i}.1,cc{i}.2'
            lines.extend([f'  have {function}{i+1} : {enclosure(function,2*u,pair)} := by',
                          f'    have lower := Real.neg_one_le_{function} {R(2*u)}',f'    have upper := Real.{function}_le_one {R(2*u)}',
                          f'    rw [show {R(2*u)} = {R(u)} + {R(u)} by norm_num, Real.{function}_add] at *',
                          f'    constructor <;> nlinarith only [{fact},lower,upper]'])
        s,c,u=ns,nc,2*u
    if tuple(map(Q,observed['sin']))!=s or tuple(map(Q,observed['cos']))!=c:raise ValueError('Native trigonometric witness reconstruction changed')
    lines.append(f'  exact ⟨sin{shifts},cos{shifts}⟩');return lines


def certify(operation,x,directory,*,bits=32,signing_key=None):
    if operation not in ('sqrt','exp','log','sin','cos','trig'):raise ValueError('Unknown analytic operation')
    x=Q(x);observed=result('math',dict(operation=operation,x=str(x),bits=bits));trig=operation in ('sin','cos','trig')
    goal='('+enclosure('sin',x,list(map(Q,observed['sin'])))+') ∧ ('+enclosure('cos',x,list(map(Q,observed['cos'])))+')' if trig else enclosure(operation,x,list(map(Q,observed['interval'])))
    if operation=='sqrt':
        lo,hi=map(Q,observed['interval']);proof=[f'  exact OmegaNative.sqrt_enclosure {R(x)} {R(lo)} {R(hi)} (by norm_num) (by norm_num) (by norm_num) (by norm_num) (by norm_num)']
    elif operation=='exp':proof=exp_proof(x,bits,observed)
    elif operation=='log':proof=log_proof(x,bits,observed)
    else:proof=trig_proof(x,bits,observed)
    source='\n'.join(['import Native.Analytic','namespace OmegaNativeMath','set_option maxRecDepth 20000','set_option maxHeartbeats 16000000',f'theorem enclosure : {goal} := by',*proof,'#print axioms enclosure','end OmegaNativeMath'])+'\n'
    root=Path(directory);root.mkdir(parents=True,exist_ok=False)
    try:obj=_compiled(source,['OmegaNativeMath.enclosure'],root)
    except Exception as error:
        if hasattr(error,'outcome'):raise ValueError('Native analytic proof rejected: '+(error.outcome.stdout+error.outcome.stderr)[-6000:]) from error
        raise
    manifest={'format':'omega-native-analytic-1','operation':operation,'x':str(x),'bits':bits,'output':observed,'lean_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'olean_sha256':hashlib.sha256(obj.read_bytes()).hexdigest()}
    from omega_selfhost.proof_protocol import encode
    envelope={'manifest':manifest,'signature':signing_key.sign(encode(manifest)).hex() if signing_key else None}
    (root/'certificate.json').write_bytes(encode(envelope));return envelope
