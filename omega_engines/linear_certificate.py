"""Fixed Lean templates for a concrete rational LP, including quantified claims.

Only exact coefficients enter this renderer; callers cannot supply declarations,
tactics, imports or hypothesis names. The numerical certificate is checked by
the separate host contract before these global linear formulas are generated.
"""
from fractions import Fraction as Q
from pathlib import Path
import hashlib

from omega_security.encoding import canonical
from omega_science.runtime import _plain, _hash, inspect_lean_transcript, ROOT
from omega_selfhost.axiom_policy import forbid_admissions
from omega_selfhost.proof import lake_binary
from omega_platform.budget import PROOF_BUDGET
from omega_platform.sandbox import trusted


def literal(value):
    value = Q(value)
    return '(('+str(value.numerator)+' : ℚ) / '+str(value.denominator)+')'


def dot(row, variables):
    if len(row) != len(variables):
        raise ValueError('LP theorem expression dimension mismatch')
    return '('+' + '.join(literal(a)+' * ('+x+')' for a,x in zip(row,variables))+')'


def render(request, observed):
    matrix = [[Q(v) for v in row] for row in request['A']]
    b = [Q(v) for v in request['b']]; c = [Q(v) for v in request['c']]
    if not 1 <= len(c) <= 12 or not 1 <= len(matrix) <= 24 or len(b) != len(matrix):
        raise ValueError('LP theorem dimension budget')
    prefix = 'import Mathlib.Tactic.Linarith\nimport Mathlib.Tactic.NormNum\nimport Mathlib.Tactic.Ring\n'
    if observed['status'] in ('optimal','infeasible'):
        name = 'engine_lp_global_bound' if observed['status']=='optimal' else 'engine_lp_infeasible'
        variables = ['x'+str(i) for i in range(len(c))]
        binders = ['('+' '.join(variables)+' : ℚ)']
        binders.extend('(hx'+str(i)+' : (0 : ℚ) ≤ '+x+')' for i,x in enumerate(variables))
        binders.extend('(ha'+str(i)+' : '+dot(row,variables)+' ≤ '+literal(bound)+')'
                       for i,(row,bound) in enumerate(zip(matrix,b)))
        conclusion = (dot(c,variables)+' ≤ '+literal(observed['objective'])) if observed['status']=='optimal' else 'False'
        source = prefix+'theorem '+name+'\n  '+'\n  '.join(binders)+' :\n  '+conclusion+' := by\n  linarith\n'
        scope = 'all feasible rational assignments for the supplied A,b,c'
    elif observed['status']=='unbounded':
        name = 'engine_lp_unbounded_ray'; x = [Q(v) for v in observed['value']]; ray = [Q(v) for v in observed['ray']]
        delta = sum((a*d for a,d in zip(c,ray)),Q(0)); base = sum((a*v for a,v in zip(c,x)),Q(0))
        if delta <= 0 or len(x)!=len(c) or len(ray)!=len(c):
            raise ValueError('Strictly improving feasible LP ray required')
        points = ['('+literal(v)+' + '+literal(d)+' * t)' for v,d in zip(x,ray)]
        claims = ['(0 : ℚ) < '+literal(delta)]
        claims.extend('(0 : ℚ) ≤ '+p for p in points)
        claims.extend(dot(row,points)+' ≤ '+literal(bound) for row,bound in zip(matrix,b))
        claims.append(dot(c,points)+' = '+literal(base)+' + '+literal(delta)+' * t')
        proofs = ['by norm_num']+['by nlinarith [ht]']*(len(claims)-2)+['by norm_num <;> ring']
        source = prefix+'theorem '+name+' (t : ℚ) (ht : 0 ≤ t) :\n  '+ ' ∧\n  '.join('('+p+')' for p in claims)+' := by\n  exact ⟨'+',\n    '.join(proofs)+'⟩\n'
        scope = 'all nonnegative rational t along a feasible ray with strictly positive objective slope'
    else:
        raise ValueError('Unknown LP theorem contract')
    source += '#print axioms '+name+'\n'
    if len(source.encode()) > 256*1024:
        raise ValueError('LP theorem source byte budget')
    forbid_admissions(source)
    return source, name, scope


def verify(request, observed, directory):
    source, name, scope = render(request,observed)
    directory = Path(directory).absolute(); directory.mkdir(parents=True,exist_ok=False)
    path = directory/'LinearContract.lean'; path.write_text(source)
    result = trusted([lake_binary(),'env','lean','--root='+str(directory),'-o',directory/'LinearContract.olean',path],
                     cwd=ROOT/'formal/tensor',budget=PROOF_BUDGET)
    (directory/'lean.log').write_text(result.stdout+result.stderr)
    if not result.ok or not (directory/'LinearContract.olean').is_file():
        raise ValueError('Lean rejected the global linear contract; partial evidence retained')
    axioms = inspect_lean_transcript(result.stdout+result.stderr,[name])
    receipt = {'format':'omega-engine-linear-contract-1','verified':True,'theorem':name,'scope':scope,
               'request_sha256':hashlib.sha256(canonical(_plain(request),max_bytes=4*1024**2,max_nodes=50000)).hexdigest(),
               'source_sha256':_hash(path),'olean_sha256':_hash(directory/'LinearContract.olean'),
               'lean_sha256':_hash(lake_binary().with_name('lean')),'axioms':axioms,
               'verifier_sha256':_hash(Path(__file__)),'compiler_refinement_proven':False}
    (directory/'receipt.json').write_bytes(canonical(receipt))
    return receipt
