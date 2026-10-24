"""Translate data-only symbolic identity certificates into closed Lean proofs.

This is a proof renderer, not a source compiler or an equality oracle. Lean must
accept every theorem before an identity is admitted. No supplied Lean code runs.
"""
from fractions import Fraction
import hashlib
import os
import shutil
from pathlib import Path
import subprocess
import tempfile


def lake_binary():
    if os.environ.get('OMEGA_LAKE'):return Path(os.environ['OMEGA_LAKE'])
    found=shutil.which('lake')
    if found:return Path(found)
    lean=os.environ.get('OMEGA_LEAN')
    if lean:return Path(lean).with_name('lake')
    return Path(__file__).resolve().parents[2]/'.tools/lean-4.19.0-linux/bin/lake'


def expand(ast,names):
    kind=ast[0]
    if kind=='n':
        q=Fraction(ast[1]);return f'(.lit (({q.numerator} : ℚ) / {q.denominator}))'
    if kind=='v':
        name=ast[1]
        if name not in names:names[name]=len(names)
        return f'(.var {names[name]})'
    if kind=='list':return [expand(a,names) for a in ast[1]]
    if kind=='un':return unary(expand(ast[2],names),lambda a:f'(.neg {a})')
    if kind=='bin':
        op=ast[1];a=expand(ast[2],names);b=expand(ast[3],names)
        if op=='+':return element(a,b,lambda x,y:f'(.add {x} {y})')
        if op=='-':return element(a,b,lambda x,y:f'(.add {x} (.neg {y}))')
        if op=='*':return element(a,b,lambda x,y:f'(.mul {x} {y})',True)
        if op=='/':
            if isinstance(b,list):raise ValueError('Tensor divisor')
            return element(a,b,lambda x,y:f'(.div {x} {y})',True)
        if op=='@':return matmul(a,b)
        if op=='^':
            n=constant(ast[3])
            if isinstance(a,list) or n.denominator!=1 or not 0<=n<=20:
                raise ValueError('Invalid power in identity')
            return f'(.pow {a} {int(n)})'
        raise ValueError('Unknown identity operation')
    if kind=='call':
        op=ast[1];args=[expand(a,names) for a in ast[2]]
        if op=='transposta' and len(args)==1:
            matrix=args[0]
            if not matrix or not all(isinstance(r,list) and len(r)==len(matrix[0]) for r in matrix):
                raise ValueError('Invalid matrix')
            return [list(row) for row in zip(*matrix)]
        if op=='dot' and len(args)==2:return dot(*args)
        if op=='soma' and len(args)==1:return sum_expr(flat(args[0]))
        if op=='relu' and len(args)==1:return unary(args[0],lambda a:f'(.relu {a})')
    raise ValueError('Malformed identity AST')


def constant(ast):
    if ast[0]=='n':return Fraction(ast[1])
    if ast[0]=='un':return -constant(ast[2])
    raise ValueError('Constant exponent required')


def unary(a,fn):return [unary(x,fn) for x in a] if isinstance(a,list) else fn(a)


def element(a,b,fn,broadcast=False):
    if not isinstance(a,list) and not isinstance(b,list):return fn(a,b)
    if isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):raise ValueError('Mismatched tensor shapes')
        return [element(x,y,fn,broadcast) for x,y in zip(a,b)]
    if not broadcast:raise ValueError('Scalar/tensor shape mismatch')
    return [element(x,b,fn,True) for x in a] if isinstance(a,list) else [element(a,y,fn,True) for y in b]


def flat(a):
    if isinstance(a,list):return [v for x in a for v in flat(x)]
    return [a]


def sum_expr(xs):
    out='(.lit 0)'
    for x in xs:out=f'(.add {out} {x})'
    return out


def dot(a,b):
    if not isinstance(a,list) or not isinstance(b,list) or len(a)!=len(b):
        raise ValueError('Mismatched vectors')
    return sum_expr([f'(.mul {x} {y})' for x,y in zip(a,b)])


def matmul(a,b):
    if not isinstance(a,list) or not a or not all(isinstance(r,list) and len(r)==len(b) for r in a):
        raise ValueError('Invalid matrix product')
    if not isinstance(b,list) or not b:raise ValueError('Empty matrix/vector')
    if not isinstance(b[0],list):return [dot(r,b) for r in a]
    bt=list(zip(*b))
    return [[dot(r,list(c)) for c in bt] for r in a]


def source(certificates):
    lines=['import TensorKernel','import Mathlib.Tactic.NormNum',
           'namespace OmegaNativeProofs','open OmegaTensor',
           'set_option maxRecDepth 10000','set_option maxHeartbeats 2000000']
    count=0
    for c in certificates:
        if set(c)!= {'tipo','left','right'} or c['tipo']!='identidade_nativa':
            raise ValueError('Unknown universal certificate schema')
        names={};a=expand(c['left'],names);b=expand(c['right'],names)
        def obligations(x,y):
            if isinstance(x,list) or isinstance(y,list):
                if not isinstance(x,list) or not isinstance(y,list) or len(x)!=len(y):
                    raise ValueError('Identity shape mismatch')
                return [pair for p,q in zip(x,y) for pair in obligations(p,q)]
            return [(x,y)]
        for x,y in obligations(a,b):
            lines.append(f'theorem identity_{count} (s : Env) : eval s {x} = eval s {y} := by\n'
                         '  simp only [eval]\n  first | rfl | ring')
            lines.append(f'#print axioms identity_{count}')
            count+=1
    lines.append('end OmegaNativeProofs')
    return '\n'.join(lines)+'\n',count


def check_identities(certificates,*,proof_path=None):
    generated,count=source(certificates)
    root=Path(os.environ.get('OMEGA_TENSOR_PROJECT',str(Path(__file__).resolve().parent.parent/'formal/tensor')))
    lake=lake_binary()
    if not lake.is_file():raise RuntimeError('Lean/Lake is required')
    with tempfile.TemporaryDirectory(prefix='omega-universal-proof-') as tmp:
        path=Path(tmp)/'Identity.lean';path.write_text(generated)
        result=subprocess.run([str(lake),'env','lean',str(path)],cwd=root,
                              capture_output=True,text=True,timeout=180)
        output=result.stdout+result.stderr
        if result.returncode or 'sorryAx' in output or 'warning:' in output:
            raise ValueError('Lean rejected the universal identity:\n'+output[-6000:])
        for i in range(count):
            if f"'OmegaNativeProofs.identity_{i}'" not in output:
                raise ValueError('Missing checked theorem')
    if proof_path is not None:
        path=Path(proof_path)
        if path.exists():raise ValueError('Proof destination already exists')
        path.write_text(generated)
    return {'theorems':count,'source_sha256':hashlib.sha256(generated.encode()).hexdigest(),
            'output':output}


def check_generated(generated):
    """Check a proof emitted by the trusted native tensor reifier."""
    root=Path(os.environ.get('OMEGA_TENSOR_PROJECT',str(Path(__file__).resolve().parent.parent/'formal/tensor')))
    lake=lake_binary()
    with tempfile.TemporaryDirectory(prefix='omega-rewrite-proof-') as tmp:
        path=Path(tmp)/'Optimization.lean';path.write_text(generated)
        proc=subprocess.run([str(lake),'env','lean',str(path)],cwd=root,
                            text=True,capture_output=True,timeout=300)
        output=proc.stdout+proc.stderr
        count=generated.count('#print axioms ')
        # Lean's generated-proof linter may report unused tactics after a goal
        # closes. Kernel rejection, admitted axioms and missing declarations
        # remain fatal; stylistic warnings do not change theorem validity.
        if proc.returncode or 'sorryAx' in output or count==0:
            raise ValueError('Lean rejected the optimization proof:\n'+output[-8000:])
        if output.count('depends on axioms:')+output.count('does not depend on any axioms')!=count:
            raise ValueError('Optimization proof output is incomplete')
    return {'theorems':count,'source_sha256':hashlib.sha256(generated.encode()).hexdigest(),
            'output':output}
