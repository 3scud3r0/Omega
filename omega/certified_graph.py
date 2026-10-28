"""Small static affine/ReLU graphs shared by export, PCI and edge backends."""
from fractions import Fraction
from .certified_proof import check, rational_literal as lit

MAX_NODES = 4096


def validate(graph):
    if type(graph) is not dict or set(graph) != {'inputs', 'nodes', 'outputs'}:
        raise ValueError('Unknown graph schema')
    n = graph['inputs']
    if type(n) is not int or not 1 <= n <= 256 or type(graph['nodes']) is not list or len(graph['nodes']) > MAX_NODES:
        raise ValueError('Static graph budget exceeded')
    for i, node in enumerate(graph['nodes'], n):
        if type(node) is not dict or node.get('op') not in ('affine', 'relu'):
            raise ValueError('Unsupported graph operation')
        if node['op'] == 'relu':
            if set(node) != {'op', 'input'} or type(node['input']) is not int or not 0 <= node['input'] < i:
                raise ValueError('Invalid ReLU reference')
        else:
            if set(node) != {'op', 'terms', 'bias'} or type(node['terms']) is not list or len(node['terms']) > 256:
                raise ValueError('Invalid affine node')
            _q(node['bias'])
            for term in node['terms']:
                if type(term) not in (tuple, list) or len(term) != 2:
                    raise ValueError('Invalid affine term')
                ref, weight = term
                if type(ref) is not int or not 0 <= ref < i:
                    raise ValueError('Invalid topological reference')
                _q(weight)
    if type(graph['outputs']) is not list or not 1 <= len(graph['outputs']) <= 256 or any(
            type(i) is not int or not 0 <= i < n + len(graph['nodes']) for i in graph['outputs']):
        raise ValueError('Invalid output references')
    return graph


def _q(value):
    if type(value) not in (str, int, Fraction) or (type(value) is str and len(value) > 3000):
        raise ValueError('Bounded exact rational required')
    q = Fraction(value)
    if max(abs(q.numerator).bit_length(), q.denominator.bit_length()) > 4096:
        raise ValueError('Rational bit budget exceeded')
    return q


def bounds_contract(bounds, count):
    if type(bounds) not in (tuple, list) or len(bounds) != count:
        raise ValueError('One interval per coordinate required')
    result = []
    for pair in bounds:
        if type(pair) not in (tuple, list) or len(pair) != 2:
            raise ValueError('Lower and upper bound required')
        lo, hi = map(_q, pair)
        if lo > hi:
            raise ValueError('Reversed interval')
        result.append((lo, hi))
    return result


def evaluate(graph, inputs):
    validate(graph)
    if len(inputs) != graph['inputs']:
        raise ValueError('Static input shape mismatch')
    values = [_q(x) for x in inputs]
    for node in graph['nodes']:
        if node['op'] == 'relu':
            values.append(max(Fraction(0), values[node['input']]))
        else:
            values.append(_q(node['bias']) + sum((_q(w) * values[r] for r, w in node['terms']), Fraction(0)))
    return [values[i] for i in graph['outputs']]


def intervals(graph, input_bounds, *, node_bounds=None):
    validate(graph)
    values = bounds_contract(input_bounds, graph['inputs'])
    supplied = bounds_contract(node_bounds, len(graph['nodes'])) if node_bounds is not None else None
    for index, node in enumerate(graph['nodes']):
        if node['op'] == 'relu':
            lo, hi = values[node['input']]
            result = (max(Fraction(0), lo), max(Fraction(0), hi))
        else:
            lo = hi = _q(node['bias'])
            for ref, raw in node['terms']:
                w = _q(raw)
                a, b = values[ref]
                lo += min(w * a, w * b)
                hi += max(w * a, w * b)
            result = (lo, hi)
        if supplied is not None:
            lo, hi = supplied[index]
            if not lo <= result[0] <= result[1] <= hi:
                raise ValueError('Unjustified local interval certificate')
            result = lo, hi
        values.append(result)
    return values


def expression(node, names):
    if node['op'] == 'relu':
        return f'(max 0 {names[node["input"]]})'
    expr = lit(node['bias'])
    for ref, weight in node['terms']:
        expr = f'({expr} + {lit(weight)} * {names[ref]})'
    return expr


def bound_source(graph, input_bounds, output_bounds, *, node_bounds=None):
    """A universal box-domain theorem, composed from local interval proofs."""
    values = intervals(graph, input_bounds, node_bounds=node_bounds)
    outputs = bounds_contract(output_bounds, len(graph['outputs']))
    for ref, (lo, hi) in zip(graph['outputs'], outputs):
        if not lo <= values[ref][0] <= values[ref][1] <= hi:
            raise ValueError('Requested output bounds are not established by interval propagation')
    names = [f'x{i}' for i in range(graph['inputs'])]
    args = ' '.join(f'({name} : ℚ)' for name in names)
    assumptions = ' '.join(f'(h{i} : {lit(lo)} ≤ {names[i]} ∧ {names[i]} ≤ {lit(hi)})'
                           for i, (lo, hi) in enumerate(values[:graph['inputs']]))
    lines = ['import ProofPrelude', 'namespace OmegaBounds',
             f'theorem bounds {args} {assumptions} :']
    expressions = list(names)
    for node in graph['nodes']:
        lines.append(f'  let x{len(expressions)} : ℚ := {expression(node, expressions)};')
        expressions.append(f'x{len(expressions)}')
    goals = [f'({lit(lo)} ≤ {expressions[ref]} ∧ {expressions[ref]} ≤ {lit(hi)})'
             for ref, (lo, hi) in zip(graph['outputs'], outputs)]
    lines += ['  ' + ' ∧ '.join(goals) + ' := by']
    for i, node in enumerate(graph['nodes'], graph['inputs']):
        name = f'x{i}'
        expr = expression(node, names)
        lo, hi = values[i]
        lines += [f'  let {name} : ℚ := {expr}',
                  f'  have h{i} : {lit(lo)} ≤ {name} ∧ {name} ≤ {lit(hi)} := by']
        if node['op'] == 'relu':
            ref = node['input']
            lower = (f'le_trans (by norm_num : {lit(lo)} ≤ {lit(values[ref][0])}) '
                     f'(le_trans h{ref}.1 (le_max_right 0 {names[ref]}))') if lo > 0 else f'le_trans (by norm_num) (le_max_left 0 {names[ref]})'
            lines += [f'    constructor', f'    · exact {lower}',
                      f'    · exact max_le (by norm_num) (le_trans h{ref}.2 (by norm_num))']
        else:
            lower = upper = 'le_refl ' + lit(node['bias'])
            low_expr = high_expr = lit(node['bias'])
            for ref, raw in node['terms']:
                w = _q(raw)
                a, b = values[ref]
                sign = 'nonneg' if w >= 0 else 'nonpos'
                lower_h, upper_h = (f'h{ref}.1', f'h{ref}.2') if w >= 0 else (f'h{ref}.2', f'h{ref}.1')
                lower = f'add_le_add ({lower}) (mul_le_mul_of_{sign}_left {lower_h} (by norm_num : {"0 ≤ " + lit(w) if w >= 0 else lit(w) + " ≤ 0"}))'
                upper = f'add_le_add ({upper}) (mul_le_mul_of_{sign}_left {upper_h} (by norm_num : {"0 ≤ " + lit(w) if w >= 0 else lit(w) + " ≤ 0"}))'
                low_expr = f'({low_expr} + {lit(w)} * {lit(a if w >= 0 else b)})'
                high_expr = f'({high_expr} + {lit(w)} * {lit(b if w >= 0 else a)})'
            lines += ['    constructor', f'    · calc {lit(lo)} ≤ {low_expr} := by norm_num',
                      f'           _ ≤ {name} := {lower}',
                      f'    · calc {name} ≤ {high_expr} := {upper}',
                      f'           _ ≤ {lit(hi)} := by norm_num']
        names.append(name)
    output_terms = [f'And.intro (le_trans (by norm_num) h{ref}.1) (le_trans h{ref}.2 (by norm_num))'
                    for ref in graph['outputs']]
    term = output_terms[-1]
    for earlier in reversed(output_terms[:-1]):
        term = f'And.intro ({earlier}) ({term})'
    lines += [f'  exact {term}', '#print axioms bounds', 'end OmegaBounds']
    return '\n'.join(lines) + '\n'


def certify_bounds(graph, input_bounds, output_bounds):
    source = bound_source(graph, input_bounds, output_bounds)
    return source, check(source, ['OmegaBounds.bounds'])


def omega_source(graph, inputs):
    validate(graph)
    if len(inputs) != graph['inputs']:
        raise ValueError('Static input shape mismatch')
    def literal(q):
        q = _q(q)
        return f'({q.numerator}/{q.denominator})'
    lines = [f'parametro x{i}={literal(q)};' for i, q in enumerate(inputs)]
    for i, node in enumerate(graph['nodes'], graph['inputs']):
        if node['op'] == 'relu':
            expr = f'relu(x{node["input"]})'
        else:
            expr = literal(node['bias']) + ''.join(f'+{literal(w)}*x{r}' for r, w in node['terms'])
        lines.append(f'tensor x{i}={expr};')
    lines += [f'mostrar x{i};' for i in graph['outputs']]
    return '\n'.join(lines) + '\n'
