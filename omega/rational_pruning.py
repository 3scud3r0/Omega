"""Continued-fraction pruning with an explicit, strict decision-margin gate.

Pruning is opt-in at a decision boundary. It is never silently applied during
backpropagation: that requires a separate propagated-error contract.
"""
from fractions import Fraction
from .certified_proof import check, rational_literal as lit


def approximate(value, *, max_denominator=2**64 - 1, max_bits=128):
    if type(value) not in (int, str, Fraction):
        raise ValueError('Exact rational required')
    q = Fraction(value)
    if type(max_denominator) is not int or not 1 <= max_denominator < 2**128:
        raise ValueError('Denominator budget must be in [1, 2^128)')
    if type(max_bits) is not int or not 2 <= max_bits <= 4096:
        raise ValueError('Bit budget must be in [2,4096]')
    reduced = q.limit_denominator(max_denominator)
    if max(abs(reduced.numerator).bit_length(), reduced.denominator.bit_length()) > max_bits:
        raise OverflowError('Magnitude cannot fit the requested rational budget')
    return reduced, abs(q - reduced)


def certify_argmax(scores, *, max_denominator=2**64 - 1, max_bits=128):
    """Return checked local error bounds and the unique unchanged decision.

    Ties and insufficient margins fail closed; no epsilon alone implies argmax.
    """
    if type(scores) not in (list, tuple) or not 2 <= len(scores) <= 256:
        raise ValueError('Between 2 and 256 scores required')
    if any(type(s) not in (int, str, Fraction) for s in scores):
        raise ValueError('Exact rational scores required')
    original = [Fraction(s) for s in scores]
    pruned, errors = zip(*(approximate(s, max_denominator=max_denominator,
                                      max_bits=max_bits) for s in original))
    winner = max(range(len(original)), key=original.__getitem__)
    if any(original[winner] - original[i] <= errors[winner] + errors[i]
           for i in range(len(original)) if i != winner):
        raise ValueError('Strict decision margin is insufficient for certified pruning')
    lines = ['import ProofPrelude', 'namespace OmegaPruning']
    names = []
    for i, (q, p, error) in enumerate(zip(original, pruned, errors)):
        name = f'OmegaPruning.error_{i}'
        lines += [f'theorem error_{i} : |{lit(q)} - {lit(p)}| ≤ {lit(error)} := by rw [abs_le]; norm_num',
                  f'#print axioms error_{i}']
        names.append(name)
        if i != winner:
            lines += [f'theorem margin_{i} : {lit(pruned[i])} < {lit(pruned[winner])} := by norm_num',
                      f'#print axioms margin_{i}']
            names.append(f'OmegaPruning.margin_{i}')
    lines.append('end OmegaPruning')
    source = '\n'.join(lines) + '\n'
    admission = check(source, names)
    return {'scores': list(map(str, original)), 'pruned': list(map(str, pruned)),
            'errors': list(map(str, errors)), 'argmax': winner,
            'scope': 'this exact score vector; strict unique argmax',
            'proof': source, 'admission': admission}


def certify_bounded_graph(graph, inputs, *, max_denominator=2**32, max_bits=128):
    """Bound intermediates by outward rounding and prove a strict final decision.

    Weights stay exact. Each arithmetic operation is followed by bounded rounding;
    interval certificates enclose the unpruned network. Correlated intervals may
    be inconclusive, in which case no decision is returned.
    """
    from .certified_graph import validate, bound_source, _q
    validate(graph)
    if len(inputs) != graph['inputs'] or len(graph['outputs']) < 2:
        raise ValueError('Static inputs and at least two outputs required')
    # Validate the public budgets even for graphs containing no affine nodes.
    approximate(0, max_denominator=max_denominator, max_bits=max_bits)
    exact = [_q(x) for x in inputs]
    values = []
    boxes = []
    def round_value(x):
        return approximate(x, max_denominator=max_denominator, max_bits=max_bits)[0]
    def outward(lo, hi):
        lower = Fraction((lo * max_denominator).__floor__(), max_denominator)
        upper = Fraction((hi * max_denominator).__ceil__(), max_denominator)
        for endpoint in (lower, upper):
            if max(abs(endpoint.numerator).bit_length(), endpoint.denominator.bit_length()) > max_bits:
                raise OverflowError('Interval magnitude exceeds pruning budget')
        return lower, upper
    for x in exact:
        values.append(round_value(x))
        boxes.append(outward(x, x))
    for node in graph['nodes']:
        if node['op'] == 'relu':
            ref = node['input']
            value = max(Fraction(0), values[ref])
            lo, hi = max(Fraction(0), boxes[ref][0]), max(Fraction(0), boxes[ref][1])
        else:
            value = round_value(Fraction(node['bias']))
            lo = hi = Fraction(node['bias'])
            for ref, raw in node['terms']:
                w = Fraction(raw)
                value = round_value(value + round_value(w * values[ref]))
                a, b = boxes[ref]
                lo += min(w*a, w*b)
                hi += max(w*a, w*b)
        values.append(value)
        boxes.append(outward(lo, hi))
    outputs = [values[i] for i in graph['outputs']]
    output_boxes = [boxes[i] for i in graph['outputs']]
    winner = max(range(len(outputs)), key=outputs.__getitem__)
    if any(output_boxes[i][1] >= output_boxes[winner][0]
           for i in range(len(outputs)) if i != winner):
        raise ValueError('Rounded interval margins cannot certify the decision')
    source = bound_source(graph, boxes[:graph['inputs']], output_boxes,
                          node_bounds=boxes[graph['inputs']:])
    # Universal dominance under the certified output intervals.
    args = ' '.join(f'(y{i} : ℚ) (h{i} : {lit(lo)} ≤ y{i} ∧ y{i} ≤ {lit(hi)})'
                    for i, (lo, hi) in enumerate(output_boxes))
    names = ['OmegaBounds.bounds']
    lines = [source, 'namespace OmegaDecision']
    for i in range(len(outputs)):
        if i == winner:
            continue
        lines += [f'theorem winner_{i} {args} : y{i} < y{winner} := by',
                  f'  exact lt_of_le_of_lt h{i}.2 (lt_of_lt_of_le (by norm_num) h{winner}.1)',
                  f'#print axioms winner_{i}']
        names.append(f'OmegaDecision.winner_{i}')
    lines.append('end OmegaDecision')
    proof = '\n'.join(lines) + '\n'
    admission = check(proof, names)
    return {'outputs': list(map(str, outputs)), 'argmax': winner,
            'input_bounds': [[str(a), str(b)] for a, b in boxes[:graph['inputs']]],
            'output_bounds': [[str(a), str(b)] for a, b in output_boxes],
            'proof': proof, 'admission': admission,
            'scope': 'forward decision for this input box; no training-gradient approximation'}
