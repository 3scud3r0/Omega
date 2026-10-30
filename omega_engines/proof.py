"""Independent finite numerical contracts; the proposer cannot select a checker."""
from fractions import Fraction as Q
from pathlib import Path
import hashlib

from omega_security.encoding import canonical
from omega_native.codec import canonical as native_document
from omega_science.runtime import _plain, _hash, build
from .runtime import run, catalog
from .execution import _receipts


def _vector(v): return [Q(x) for x in v]
def _matrix(m): return [_vector(row) for row in m]
def _dot(a, b):
    if len(a) != len(b): raise ValueError('Independent contract dot shape')
    return sum((x*y for x, y in zip(a, b)), Q(0))
def _transpose(a): return [list(row) for row in zip(*a)]
def _multiply(a, b): return [[_dot(row, col) for col in _transpose(b)] for row in a]
def _apply(a, x): return [_dot(row, x) for row in a]


def _poly_derivative_value(terms, point, first, second=None):
    total = Q(0)
    for coefficient, exponents in terms:
        e = [int(Q(x)) for x in exponents]; coefficient = Q(coefficient)
        for index in ([first] if second is None else [first, second]):
            coefficient *= e[index]; e[index] -= 1
        if not coefficient: continue
        for x, power in zip(point, e): coefficient *= x**power
        total += coefficient
    return total


def _lp(request, observed):
    matrix = _matrix(request['A']); b = _vector(request['b']); c = _vector(request['c'])
    status = observed['status']; witnesses = []
    def nonnegative(v):
        if v < 0: raise ValueError('Independent LP certificate has a negative slack')
        witnesses.append({'nonnegative': v})
    if status == 'infeasible':
        y = observed['farkas']
        if len(y) != len(b): raise ValueError('Farkas certificate shape')
        for v in y: nonnegative(v)
        for column in _transpose(matrix):
            value = _dot(column, y); nonnegative(value)
            witnesses.append({'left_dot': [column, y], 'right': [value]})
        contradiction = _dot(b, y)
        if contradiction >= 0: raise ValueError('Independent Farkas contradiction is missing')
        if observed['contradiction'] != contradiction: raise ValueError('Incorrect reported Farkas value')
        witnesses.extend(({'left_dot': [b, y], 'right': [contradiction]}, {'nonnegative': -contradiction}))
        return witnesses
    x = observed['value']
    if len(x) != len(c): raise ValueError('Primal certificate shape')
    for v in x: nonnegative(v)
    for row, bound in zip(matrix, b):
        value = _dot(row, x); nonnegative(bound-value)
        witnesses.append({'left_dot': [row, x], 'right': [value]})
    if status == 'unbounded':
        ray = observed['ray']
        if len(ray) != len(c) or _dot(c, ray) <= 0: raise ValueError('Invalid recession direction')
        for v in ray: nonnegative(v)
        for row in matrix:
            value = _dot(row, ray); nonnegative(-value)
            witnesses.append({'left_dot': [row, ray], 'right': [value]})
        witnesses.append({'nonnegative': _dot(c, ray)})
        return witnesses
    if status != 'optimal': raise ValueError('Unknown LP certificate status')
    y = observed['dual']
    if len(y) != len(b): raise ValueError('Dual certificate shape')
    for v in y: nonnegative(v)
    for column, objective in zip(_transpose(matrix), c):
        value = _dot(column, y); nonnegative(value-objective)
        witnesses.append({'left_dot': [column, y], 'right': [value]})
    if _dot(c,x) != _dot(b,y): raise ValueError('Independent duality gap is nonzero')
    if observed['objective'] != _dot(c,x) or observed['duality_gap'] != 0:
        raise ValueError('Incorrect reported objective or duality gap')
    witnesses.append({'left_dot': [c,x], 'right_dot': [b,y]})
    return witnesses


def _action(request, observed):
    if request['mode'] != 'simulate': raise ValueError('Action proof supports the reviewed variational simulation contract')
    q = _vector(request['position']); mass = _vector(request['mass']); h = Q(request['dt']); d = len(q)
    potential = request['potential']; nextq = observed['value'][0][0]
    if len(observed['value']) != int(Q(request['steps'])):
        raise ValueError('Variational trace length differs from requested steps')
    h0 = [[_poly_derivative_value(potential,q,i,j) for j in range(d)] for i in range(d)]
    h1 = [[_poly_derivative_value(potential,nextq,i,j) for j in range(d)] for i in range(d)]
    identity = [[Q(int(i==j)) for j in range(2*d)] for i in range(2*d)]
    kick0 = [row[:] for row in identity]; kick1 = [row[:] for row in identity]; drift = [row[:] for row in identity]
    form = [[Q(0) for _ in range(2*d)] for _ in range(2*d)]
    for i in range(d):
        drift[i][d+i] = h/mass[i]; form[i][d+i] = 1; form[d+i][i] = -1
        for j in range(d): kick0[d+i][j] = -h*h0[i][j]/2; kick1[d+i][j] = -h*h1[i][j]/2
    jacobian = _multiply(kick1,_multiply(drift,kick0))
    if jacobian != observed['jacobian_at_initial_state']: raise ValueError('Independent variational Jacobian mismatch')
    jt = _transpose(jacobian); fj = _multiply(form,jacobian); witnesses = []
    position = q[:]; momentum = _vector(request['momentum'])
    for actual_q,actual_p,_ in observed['value']:
        gradient = [_poly_derivative_value(potential,position,i) for i in range(d)]
        expected_q = [position[i]+h*(momentum[i]-h*gradient[i]/2)/mass[i] for i in range(d)]
        next_gradient = [_poly_derivative_value(potential,expected_q,i) for i in range(d)]
        expected_p = [momentum[i]-h*(gradient[i]+next_gradient[i])/2 for i in range(d)]
        if actual_q != expected_q or actual_p != expected_p:
            raise ValueError('Independent kick-drift-kick trajectory differs from observation')
        for i in range(d):
            witnesses.append({'left_dot': [[position[i],momentum[i],gradient[i]],[1,h/mass[i],-h*h/(2*mass[i])]],
                              'right': [actual_q[i]]})
            witnesses.append({'left_dot': [[momentum[i],gradient[i],next_gradient[i]],[1,-h/2,-h/2]],
                              'right': [actual_p[i]]})
        position, momentum = actual_q, actual_p
    for i in range(2*d):
        for j in range(i,2*d):
            column = _transpose(fj)[j]
            witnesses.append({'left_dot': [jt[i],column], 'right': [form[i][j]]})
    positions = [q, *[record[0] for record in observed['value']]]
    for previous,current,next_position in zip(positions,positions[1:],positions[2:]):
        for i in range(d):
            gradient = _poly_derivative_value(potential,current,i)
            witnesses.append({'left_dot': [[2*current[i],-previous[i],-next_position[i]], [mass[i]/h]*3],
                              'right': [h*gradient]})
    return witnesses


def _coarse(request, observed):
    if request['mode'] == 'coarse':
        values = _vector(request['values']); weights = _vector(request['weights']); groups = [int(Q(x)) for x in request['groups']]
        means = observed['value']; mass = [sum((w for w,g in zip(weights,groups) if g==i),Q(0)) for i in range(len(means))]
        sums = [sum((v*w for v,w,g in zip(values,weights,groups) if g==i),Q(0)) for i in range(len(means))]
        if any(m<=0 or mean*m!=s for mean,m,s in zip(means,mass,sums)): raise ValueError('Independent conservative block mean failed')
        unresolved = sum((w*(v-means[g])**2 for v,w,g in zip(values,weights,groups)),Q(0))
        return [{'left_dot': [weights,[v*v for v in values]],
                 'right': [unresolved,*[m*x*x for m,x in zip(mass,means)]]}]
    if request['mode'] != 'gaussian' or 'slow_state' not in request:
        raise ValueError('Gaussian coarse-graining proof requires an explicit slow-state probe')
    slow = _vector(request['slow_state']); fast = observed['fast_state']; full = slow+fast
    h = _matrix(request['hessian']); b = _vector(request['linear']); constant = Q(request.get('constant',0))
    original = _dot(full,_apply(h,full))/2+_dot(b,full)+constant
    effective = _dot(slow,_apply(observed['value'],slow))/2+_dot(observed['linear'],slow)+observed['constant']
    if original != effective: raise ValueError('Independent Schur energy equivalence failed')
    left_coefficients = []; left_terms = []; right_coefficients = []; right_terms = []
    for i in range(len(full)):
        for j in range(len(full)): left_coefficients.append(h[i][j]/2); left_terms.append(full[i]*full[j])
    left_coefficients.extend(b+[constant]); left_terms.extend(full+[Q(1)])
    for i in range(len(slow)):
        for j in range(len(slow)): right_coefficients.append(observed['value'][i][j]/2); right_terms.append(slow[i]*slow[j])
    right_coefficients.extend(observed['linear']+[observed['constant']]); right_terms.extend(slow+[Q(1)])
    return [{'left_dot': [left_coefficients,left_terms], 'right_dot': [right_coefficients,right_terms]}]


def prove(identifier, request, destination):
    if type(identifier) is not int or identifier not in (3,6,7):
        raise ValueError('No reviewed numeric proof contract for this engine; use run')
    request = _plain(request)
    entry = next(e for e in catalog()['engines'] if e['id']==identifier)
    binary = build(entry['group']); binary_hash = _hash(binary)
    observed = run(identifier, request)
    if build(entry['group']) != binary or _hash(binary) != binary_hash:
        raise ValueError('Engine build changed while extracting numeric obligations')
    witnesses = {3:_lp,6:_action,7:_coarse}[identifier](request,observed)
    if not 1 <= len(witnesses) <= 256: raise ValueError('Numeric proof obligation budget 1..256')
    directory = Path(destination).absolute(); directory.mkdir(parents=True,exist_ok=False)
    (directory/'request.json').write_bytes(canonical(request,max_bytes=4*1024**2,max_nodes=50000))
    (directory/'observation.json').write_text(native_document(observed))
    receipts = _receipts(witnesses,directory/'proof')
    result = {'format':'omega-engine-numeric-proof-1','engine':identifier,'verified':True,
              'obligations':len(witnesses),'proof_batches':len(receipts),'binary_sha256':binary_hash,
              'request_sha256':hashlib.sha256(canonical(request,max_bytes=4*1024**2,max_nodes=50000)).hexdigest(),
              'verifier_sha256':_hash(Path(__file__)),
              'scientific_model_accepted':False,'compiler_refinement_proven':False,'promoted':False,
              'files':{str(p.relative_to(directory)):_hash(p) for p in sorted(directory.rglob('*')) if p.is_file()}}
    (directory/'receipt.json').write_bytes(canonical(result))
    return result
