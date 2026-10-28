"""Real graph enclosure, rational execution and Lean error propagation."""
from fractions import Fraction as Q
from .certified_graph import validate, bounds_contract, _q
from .transcendental import exp_enclosure, rsqrt_enclosure, outward, real, ProofBuilder


def product(a, b):
    corners = [x*y for x in a for y in b]
    return min(corners), max(corners)


def probability_terms(graph, node, values):
    if node['op'] != 'div' or node['right'] < graph['inputs']:
        return None
    denominator = graph['nodes'][node['right']-graph['inputs']]
    if (denominator['op'] != 'affine' or Q(denominator['bias']) != 0
            or not denominator['terms'] or any(Q(w) != 1 or values[r][0] < 0 for r, w in denominator['terms'])
            or node['left'] not in [r for r, _ in denominator['terms']]):
        return None
    return denominator['terms']


def analyze(graph, input_bounds):
    validate(graph)
    values = bounds_contract(input_bounds, graph['inputs'])
    details = []
    bits = graph.get('precision_bits', 32)
    for node in graph['nodes']:
        op = node['op']
        detail = None
        if op == 'affine':
            low = high = Q(node['bias'])
            for ref, weight in node['terms']:
                a, b = product(values[ref], (Q(weight), Q(weight)))
                low, high = low + a, high + b
        elif op == 'relu':
            a, b = values[node['input']]
            low, high = max(Q(0), a), max(Q(0), b)
        elif op == 'square':
            a, b = values[node['input']]
            low, high = (Q(0) if a <= 0 <= b else min(a*a, b*b)), max(a*a, b*b)
        elif op == 'mul':
            low, high = product(values[node['left']], values[node['right']])
        elif op == 'div':
            a, b = values[node['right']]
            if a <= 0:
                raise ValueError('Division requires a strictly positive certified denominator')
            low, high = product(values[node['left']], (1/b, 1/a))
            if probability_terms(graph, node, values) is not None:
                low, high = max(Q(0), low), min(Q(1), high)
        elif op == 'exp':
            a, b = values[node['input']]
            low, _, _ = exp_enclosure(a, bits=bits + 0)
            _, high, _ = exp_enclosure(b, bits=bits + 0)
        elif op == 'rsqrt':
            a, b = values[node['input']]
            low, high, detail = rsqrt_enclosure(a, b, bits=bits)
        else:
            raise ValueError('Unknown real graph operation')
        rounded = outward(low, high, bits + 16)
        if low > 0 and rounded[0] <= 0:
            # Positive lower endpoints must remain positive; do not round to zero.
            rounded = low, rounded[1]
        values.append(rounded)
        details.append(detail)
    return values, details


def execute(graph, inputs):
    validate(graph)
    if len(inputs) != graph['inputs']:
        raise ValueError('Static input shape mismatch')
    values = [_q(x) for x in inputs]
    bits = graph.get('precision_bits', 32)
    for node in graph['nodes']:
        op = node['op']
        if op == 'affine':
            value = Q(node['bias']) + sum((Q(w)*values[r] for r, w in node['terms']), Q(0))
        elif op == 'relu':
            value = max(Q(0), values[node['input']])
        elif op == 'square':
            value = values[node['input']] ** 2
        elif op == 'mul':
            value = values[node['left']] * values[node['right']]
        elif op == 'div':
            denominator = values[node['right']]
            if denominator <= 0:
                raise ValueError('Rational execution denominator is not positive')
            value = values[node['left']] / denominator
        elif op in ('exp', 'rsqrt'):
            args = values[node['input']]
            a, b, _ = exp_enclosure(args, bits=bits) if op == 'exp' else rsqrt_enclosure(args, bits=bits)
            value = (a+b) / 2
            # Store a dyadic approximation; its discrepancy is checked against
            # the independently enclosed ideal real graph before certification.
            value = Q(round(value * (1 << (bits + 8))), 1 << (bits + 8))
            if value == 0:
                value = Q(1,1 << (bits+8))
        else:
            raise ValueError('Unknown graph operation')
        if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > 16384:
            raise OverflowError('Rational execution bit budget exceeded')
        values.append(value)
    return values


def expression(node, names):
    op = node['op']
    if op == 'affine':
        value = real(node['bias'])
        for ref, weight in node['terms']:
            value = f'({value} + {real(weight)} * {names[ref]})'
        return value
    if op == 'relu':
        return f'(max 0 {names[node["input"]]})'
    if op == 'square':
        return f'({names[node["input"]]} * {names[node["input"]]})'
    if op == 'exp':
        return f'(Real.exp {names[node["input"]]})'
    if op == 'rsqrt':
        return f'(1 / Real.sqrt {names[node["input"]]})'
    return f'({names[node["left"]]} {"*" if op == "mul" else "/"} {names[node["right"]]})'


def _mul_term(x, y, a, b, output, hx, hy):
    low, high = output
    args = ' '.join(map(real, (*a, *b, low, high)))
    return f'OmegaReal.mul_bounds {x} {y} {args} {hx} {hy} ' + ' '.join(['(by norm_num)']*8)


def render_bounds(builder, graph, input_bounds, output_bounds, label):
    values, details = analyze(graph, input_bounds)
    required = bounds_contract(output_bounds, len(graph['outputs']))
    for ref, (a, b) in zip(graph['outputs'], required):
        if not a <= values[ref][0] <= values[ref][1] <= b:
            raise ValueError('Real graph does not establish the requested output contract')
    endpoint_names = {}
    for i, node in enumerate(graph['nodes'], graph['inputs']):
        if node['op'] == 'exp':
            a, b = values[node['input']]
            endpoint_names[i] = builder.exp_endpoint(a, graph.get('precision_bits', 32)), builder.exp_endpoint(b, graph.get('precision_bits', 32))
    names = [f'x{i}' for i in range(graph['inputs'])]
    args = ' '.join(f'({n} : ℝ)' for n in names)
    hypotheses = ' '.join(f'(h{i} : {real(a)} ≤ x{i} ∧ x{i} ≤ {real(b)})' for i, (a, b) in enumerate(values[:graph['inputs']]))
    lines = [f'theorem {label} {args} {hypotheses} :']
    declared = list(names)
    for node in graph['nodes']:
        lines.append(f'  let x{len(declared)} : ℝ := {expression(node, declared)};')
        declared.append(f'x{len(declared)}')
    goals = [f'({real(a)} ≤ x{ref} ∧ x{ref} ≤ {real(b)})' for ref, (a, b) in zip(graph['outputs'], required)]
    lines.append('  ' + ' ∧ '.join(goals) + ' := by')
    for i, node in enumerate(graph['nodes'], graph['inputs']):
        lo, hi = values[i]
        op = node['op']
        lines += [f'  let x{i} : ℝ := {expression(node, names)}',
                  f'  have h{i} : {real(lo)} ≤ x{i} ∧ x{i} ≤ {real(hi)} := by']
        if op == 'affine':
            lower = upper = f'le_refl {real(node["bias"])}'
            le = ue = real(node['bias'])
            for ref, weight in node['terms']:
                w = Q(weight)
                a, b = values[ref]
                sign = 'nonneg' if w >= 0 else 'nonpos'
                lh, uh = (1, 2) if w >= 0 else (2, 1)
                premise = f'0 ≤ {real(w)}' if w >= 0 else f'{real(w)} ≤ 0'
                lower = f'add_le_add ({lower}) (mul_le_mul_of_{sign}_left h{ref}.{lh} (by norm_num : {premise}))'
                upper = f'add_le_add ({upper}) (mul_le_mul_of_{sign}_left h{ref}.{uh} (by norm_num : {premise}))'
                le = f'({le} + {real(w)} * {real(a if w >= 0 else b)})'
                ue = f'({ue} + {real(w)} * {real(b if w >= 0 else a)})'
            lines += ['    constructor', f'    · calc {real(lo)} ≤ {le} := by norm_num', f'           _ ≤ x{i} := {lower}',
                      f'    · calc x{i} ≤ {ue} := {upper}', f'           _ ≤ {real(hi)} := by norm_num']
        elif op == 'relu':
            ref = node['input']
            a, b = values[ref]
            lower = f'le_trans (by norm_num : {real(lo)} ≤ {real(a)}) (le_trans h{ref}.1 (le_max_right 0 x{ref}))' if lo > 0 else f'le_trans (by norm_num) (le_max_left 0 x{ref})'
            lines += [f'    exact ⟨{lower}, max_le (by norm_num) (le_trans h{ref}.2 (by norm_num))⟩']
        elif op == 'mul':
            l, r = node['left'], node['right']
            lines.append('    exact ' + _mul_term(f'x{l}', f'x{r}', values[l], values[r], (lo, hi), f'h{l}', f'h{r}'))
        elif op == 'square':
            ref = node['input']
            a, b = values[ref]
            raw = min(a*a, a*b, b*b)
            lines += ['    constructor']
            if a <= 0 <= b:
                lines.append(f'    · exact le_trans (by norm_num : {real(lo)} ≤ 0) (mul_self_nonneg x{ref})')
            else:
                term = _mul_term(f'x{ref}', f'x{ref}', (a, b), (a, b), (lo, hi), f'h{ref}', f'h{ref}')
                lines.append(f'    · exact ({term}).1')
            term = _mul_term(f'x{ref}', f'x{ref}', (a, b), (a, b), (raw, hi), f'h{ref}', f'h{ref}')
            lines.append(f'    · exact ({term}).2')
        elif op == 'div':
            l, r = node['left'], node['right']
            a, b = values[r]
            probability = probability_terms(graph, node, values)
            if probability is not None:
                denominator = graph['nodes'][r-graph['inputs']]
                premises = ', '.join(f'h{ref}.1' for ref, _ in probability)
                lines += [f'    have positive : 0 < x{r} := lt_of_lt_of_le (by norm_num : 0 < {real(a)}) h{r}.1',
                          f'    have numerator_nonneg : 0 ≤ x{l} := le_trans (by norm_num) h{l}.1',
                          f'    have comparison : x{l} ≤ x{r} := by',
                          f'      change x{l} ≤ {expression(denominator, names)}',
                          f'      linarith only [{premises}]',
                          f'    have bounded : x{l}/x{r} ≤ 1 := (div_le_one positive).2 comparison']
                # Lower bounds retain the tighter interval result. Upper 1 is
                # proved using the actual shared denominator, not independence.
                raw_low, raw_high = product(values[l], (1/b, 1/a))
                term = _mul_term(f'x{l}', f'(1/x{r})', values[l], (1/b, 1/a), (lo, max(hi, raw_high)), f'h{l}', 'invh')
                lines += [f'    have invh : {real(1/b)} ≤ 1/x{r} ∧ 1/x{r} ≤ {real(1/a)} := by',
                          f'      have raw := OmegaReal.inv_bounds x{r} {real(a)} {real(b)} (by norm_num) h{r}',
                          '      convert raw using 1 <;> norm_num',
                          f'    constructor', f'    · simpa only [div_eq_mul_inv, one_mul] using ({term}).1']
                if hi >= 1:
                    lines.append('    · exact le_trans bounded (by norm_num)')
                else:
                    term = _mul_term(f'x{l}', f'(1/x{r})', values[l], (1/b, 1/a), (min(lo, raw_low), hi), f'h{l}', 'invh')
                    lines.append(f'    · simpa only [div_eq_mul_inv, one_mul] using ({term}).2')
            else:
                lines += [f'    have invh : {real(1/b)} ≤ 1/x{r} ∧ 1/x{r} ≤ {real(1/a)} := by',
                          f'      have raw := OmegaReal.inv_bounds x{r} {real(a)} {real(b)} (by norm_num) h{r}',
                          '      convert raw using 1 <;> norm_num',
                          '    simpa only [div_eq_mul_inv, one_mul] using (' + _mul_term(f'x{l}', f'(1/x{r})', values[l], (1/b, 1/a), (lo, hi), f'h{l}', 'invh') + ')']
        elif op == 'rsqrt':
            ref = node['input']
            a, b = values[ref]
            s, t = details[i-graph['inputs']]
            lines += [f'    have root := OmegaReal.rsqrt_bounds x{ref} {real(a)} {real(b)} {real(s)} {real(t)} (by norm_num) (by norm_num) (by norm_num) h{ref} (by norm_num) (by norm_num)',
                      '    exact ⟨le_trans (by norm_num) root.1, le_trans root.2 (by norm_num)⟩']
        elif op == 'exp':
            ref = node['input']
            a, b = values[ref]
            (_, _, left), (_, _, right) = endpoint_names[i]
            lines += [f'    exact OmegaReal.exp_interval x{ref} {real(a)} {real(b)} {real(lo)} {real(hi)} h{ref}',
                      f'      (le_trans (by norm_num) {left}.1) (le_trans {right}.2 (by norm_num))']
        names.append(f'x{i}')
    terms = [f'And.intro (le_trans (by norm_num) h{ref}.1) (le_trans h{ref}.2 (by norm_num))' for ref in graph['outputs']]
    term = terms[-1]
    for first in reversed(terms[:-1]):
        term = f'And.intro ({first}) ({term})'
    lines += [f'  exact {term}', f'#print axioms {label}']
    builder.lines += lines
    builder.names.append('OmegaApprox.'+label)
    return values


def bounds_proof(graph, input_bounds, output_bounds):
    builder = ProofBuilder()
    render_bounds(builder, graph, input_bounds, output_bounds, 'domain_bounds')
    return builder.finish(), builder.names


def certify(graph, inputs, input_bounds, output_bounds, max_error):
    from .certified_proof import check
    if len(inputs) != graph['inputs']:
        raise ValueError('Static input shape mismatch')
    inputs = [_q(x) for x in inputs]
    domain = bounds_contract(input_bounds, graph['inputs'])
    if any(not a <= x <= b for x, (a, b) in zip(inputs, domain)):
        raise ValueError('Input outside certified domain')
    errors = [_q(max_error)]*len(graph['outputs']) if type(max_error) in (str, int, Q) else [_q(x) for x in max_error]
    if len(errors) != len(graph['outputs']) or any(x <= 0 for x in errors):
        raise ValueError('One strictly positive error budget per output required')
    computed = execute(graph, inputs)
    builder = ProofBuilder()
    render_bounds(builder, graph, domain, output_bounds, 'domain_bounds')
    boxes, _ = analyze(graph, [(x, x) for x in inputs])
    target = [boxes[i] for i in graph['outputs']]
    render_bounds(builder, graph, [(x, x) for x in inputs], target, 'point_bounds')
    differences = []
    for ref, (a, b), budget in zip(graph['outputs'], target, errors):
        error = max(abs(computed[ref]-a), abs(computed[ref]-b))
        if error > budget:
            raise ValueError(f'Output approximation error {error} exceeds requested budget {budget}')
        differences.append(error)
    names = [real(x) for x in inputs]
    body = [f'theorem execution_error :']
    for node in graph['nodes']:
        body.append(f'  let v{len(names)} : ℝ := {expression(node, names)};')
        names.append(f'v{len(names)}')
    goals = [f'(|{names[ref]} - {real(computed[ref])}| ≤ {real(budget)})' for ref, budget in zip(graph['outputs'], errors)]
    body += ['  ' + ' ∧ '.join(goals) + ' := by']
    names = [real(x) for x in inputs]
    for node in graph['nodes']:
        body.append(f'  let v{len(names)} : ℝ := {expression(node, names)}')
        names.append(f'v{len(names)}')
    bounds_goal = ' ∧ '.join(f'({real(a)} ≤ {names[ref]} ∧ {names[ref]} ≤ {real(b)})' for ref, (a, b) in zip(graph['outputs'], target))
    args = ' '.join(map(real, inputs)) + ' ' + ' '.join(['(by norm_num)']*len(inputs))
    body.append(f'  have all_bounds : {bounds_goal} := point_bounds {args}')
    count = len(graph['outputs'])
    for i, (ref, budget) in enumerate(zip(graph['outputs'], errors)):
        path = 'all_bounds' + '.2'*i + ('.1' if i < count-1 else '')
        if count == 1:
            path = 'all_bounds'
        body += [f'  have out{i} := {path}',
                 f'  have error{i} : |{names[ref]} - {real(computed[ref])}| ≤ {real(budget)} := by',
                 f'    rw [abs_le]', f'    constructor <;> linarith only [out{i}.1, out{i}.2]']
    term = f'error{count-1}'
    for i in reversed(range(count-1)):
        term = f'And.intro error{i} ({term})'
    body += [f'  exact {term}', '#print axioms execution_error']
    builder.lines += body
    builder.names.append('OmegaApprox.execution_error')
    proof = builder.finish()
    return {'outputs': [str(computed[i]) for i in graph['outputs']],
            'error_bounds': list(map(str, differences)), 'max_error': list(map(str, errors)),
            'proof': proof, 'admission': check(proof, builder.names)}


def omega_program(graph, inputs):
    values = execute(graph, inputs)
    def lit(x):
        x = Q(x)
        return f'({x.numerator}/{x.denominator})'
    lines = [f'parametro x{i}={lit(x)};' for i, x in enumerate(values[:graph['inputs']])]
    for i, node in enumerate(graph['nodes'], graph['inputs']):
        op = node['op']
        if op == 'affine':
            expr = lit(node['bias']) + ''.join(f'+{lit(w)}*x{r}' for r, w in node['terms'])
        elif op == 'relu':
            expr = f'relu(x{node["input"]})'
        elif op == 'square':
            expr = f'x{node["input"]}*x{node["input"]}'
        elif op in ('mul', 'div'):
            expr = f'x{node["left"]}{"*" if op == "mul" else "/"}x{node["right"]}'
        else:
            expr = lit(values[i])
        lines.append(f'tensor x{i}={expr};')
    lines += [f'mostrar x{i};' for i in graph['outputs']]
    return '\n'.join(lines) + '\n'
