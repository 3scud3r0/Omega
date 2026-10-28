"""Rational enclosures of real exp and inverse sqrt, with reconstructible proofs.

No floating-point library supplies a certificate endpoint. Taylor remainders,
range reduction, integer square roots and outward dyadic rounding are exact.
"""
from fractions import Fraction as Q
from math import factorial, isqrt

from .certified_graph import _q


def precision(bits):
    if type(bits) is not int or not 8 <= bits <= 128:
        raise ValueError('Precision must be an integer in [8,128] bits')
    return bits


def outward(low, high, bits):
    scale = 1 << bits
    return Q((low * scale).__floor__(), scale), Q((high * scale).__ceil__(), scale)


def exp_enclosure(value, *, bits=32):
    bits = precision(bits)
    value = _q(value)
    if abs(value) > 32:
        raise ValueError('Certified exponential domain is [-32,32]')
    if value == 0:
        return Q(1), Q(1), {'value': '0', 'terms': 0, 'steps': []}
    absolute = abs(value)
    reductions = 0
    while absolute / (1 << reductions) > 1:
        reductions += 1
    t = absolute / (1 << reductions)
    work_bits = bits + 2 * int(absolute.__ceil__()) + 24
    for terms in range(12, 65, 4):
        polynomial = sum((t**j / factorial(j) for j in range(terms)), Q(0))
        tail = t**terms * Q(terms + 1, factorial(terms) * terms)
        low, high = polynomial - tail, polynomial + tail
        if low <= 0:
            continue
        steps = [(low, high)]
        for _ in range(reductions):
            low, high = outward(low * low, high * high, work_bits)
            steps.append((low, high))
        if value < 0:
            low, high = 1 / high, 1 / low
        if high - low <= Q(1, 1 << bits):
            return low, high, {'value': str(value), 'terms': terms,
                               'steps': [[str(a), str(b)] for a, b in steps]}
    raise ValueError('Taylor budget exhausted before requested precision')


def sqrt_bracket(value, *, bits=32):
    value = _q(value)
    if value <= 0:
        raise ValueError('Strictly positive square-root domain required')
    bits = precision(bits)
    while bits <= 256:
        scale = 1 << bits
        lower = isqrt((value.numerator * scale * scale) // value.denominator)
        if lower:
            return Q(lower, scale), Q(lower + 1, scale)
        bits += 8
    raise ValueError('Square-root scale budget exhausted')


def rsqrt_enclosure(low, high=None, *, bits=32):
    low, high = _q(low), _q(low if high is None else high)
    if not 0 < low <= high:
        raise ValueError('Inverse sqrt requires a strictly positive interval')
    a, _ = sqrt_bracket(low, bits=bits)
    _, b = sqrt_bracket(high, bits=bits)
    return 1 / b, 1 / a, (a, b)


def real(value):
    value = Q(value)
    return f'(({value.numerator} : ℝ) / {value.denominator})'


class ProofBuilder:
    """Trusted rendering from exact, bounded data; never accepts supplied Lean."""
    def __init__(self):
        self.lines = ['import Omega.Transcendental', 'namespace OmegaApprox',
                      'set_option maxRecDepth 20000', 'set_option maxHeartbeats 8000000']
        self.names = []
        self.cache = {}

    def exp_endpoint(self, value, bits=32):
        value = Q(value)
        key = value, bits
        if key in self.cache:
            return self.cache[key]
        low, high, witness = exp_enclosure(value, bits=bits)
        name = f'exp_{len(self.cache)}'
        self.lines += [f'theorem {name} : {real(low)} ≤ Real.exp {real(value)} ∧ Real.exp {real(value)} ≤ {real(high)} := by']
        if value == 0:
            self.lines.append('  norm_num')
        else:
            steps = [(Q(a), Q(b)) for a, b in witness['steps']]
            t = abs(value) / (1 << (len(steps) - 1))
            n = witness['terms']
            a, b = steps[0]
            self.lines += [f'  have z0 : {real(a)} ≤ Real.exp {real(t)} ∧ Real.exp {real(t)} ≤ {real(b)} := by',
                           f'    have positive : 0 ≤ {real(t)} := by norm_num',
                           f'    have unit : |{real(t)}| ≤ 1 := by rw [abs_of_nonneg positive]; norm_num',
                           f'    have h := Real.exp_bound (x := {real(t)}) (n := {n}) unit (by norm_num)',
                           '    norm_num [abs_of_nonneg positive, Finset.sum_range_succ, Nat.factorial] at h',
                           '    have h1 := (abs_le.mp h).1', '    have h2 := (abs_le.mp h).2',
                           '    constructor <;> linarith only [h1, h2]']
            for i, (a, b) in enumerate(steps[1:], 1):
                old = t
                t *= 2
                l, u = steps[i-1]
                self.lines += [f'  have z{i} : {real(a)} ≤ Real.exp {real(t)} ∧ Real.exp {real(t)} ≤ {real(b)} := by',
                               f'    rw [show {real(t)} = {real(old)} + {real(old)} by norm_num]',
                               f'    exact OmegaReal.exp_double {real(old)} {real(l)} {real(u)} {real(a)} {real(b)} (by norm_num) z{i-1} (by norm_num) (by norm_num)']
            last = len(steps) - 1
            if value > 0:
                self.lines.append(f'  exact z{last}')
            else:
                l, u = steps[-1]
                self.lines += [f'  rw [show {real(value)} = -{real(abs(value))} by norm_num, Real.exp_neg]',
                               f'  have invh := OmegaReal.inv_bounds (Real.exp {real(abs(value))}) {real(l)} {real(u)} (by norm_num) z{last}',
                               '  convert invh using 1 <;> norm_num [one_div]']
        self.lines.append(f'#print axioms {name}')
        self.names.append('OmegaApprox.' + name)
        self.cache[key] = low, high, name
        return self.cache[key]

    def finish(self):
        return '\n'.join(self.lines + ['end OmegaApprox']) + '\n'


def certify_softmax_argmax(logits, *, max_denominator=2**64-1, max_bits=128):
    """Prove classification invariance without approximating any exponential."""
    from .rational_pruning import certify_argmax
    from .certified_proof import check
    local = certify_argmax(logits,max_denominator=max_denominator,max_bits=max_bits)
    scores = [_q(x) for x in logits]
    count,winner=len(scores),local['argmax']
    expr=real(scores[-1])
    for i in reversed(range(count-1)):
        expr=f'if i.val = {i} then {real(scores[i])} else ({expr})'
    lines=['import Omega.Transcendental','namespace OmegaClassification',
           f'noncomputable def logits : Fin {count} → ℝ := fun i => {expr}']
    names=[]
    for i in range(count):
        if i==winner:continue
        lines += [f'theorem winner_{i} : OmegaReal.softmax logits ⟨{i}, by decide⟩ < OmegaReal.softmax logits ⟨{winner}, by decide⟩ := by',
                  f'  apply (OmegaReal.softmax_order logits ⟨{i}, by decide⟩ ⟨{winner}, by decide⟩).2',
                  '  norm_num [logits]',f'#print axioms winner_{i}']
        names.append(f'OmegaClassification.winner_{i}')
    lines.append('end OmegaClassification');source='\n'.join(lines)+'\n'
    return {**local,'softmax_proof':source,'softmax_admission':check(source,names),
            'scope':'unique argmax of these rational logits, their certified pruning and their exact real Softmax'}
