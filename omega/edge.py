"""Heap-free, freestanding int64 backend with exact static rational scales.

Each node has a compile-time scale. No rounding occurs: scale growth or a
potential overflowing product/partial sum rejects export. No OS/GMP is needed.
"""
from fractions import Fraction
from pathlib import Path
from .certified_graph import intervals, certify_bounds, validate, real_operations

LIMIT = 2**63 - 1


def emit(graph, input_bounds, output_bounds, directory, *, input_scale=1):
    import math
    import json
    validate(graph)
    if real_operations(graph):
        raise ValueError('Freestanding static-scale backend accepts affine/ReLU graphs; use the GMP real runtime for transcendental graphs')
    values = intervals(graph, input_bounds)
    if type(input_scale) is not int or not 1 <= input_scale <= LIMIT:
        raise ValueError('A positive int64 input scale is required')
    scales = [input_scale] * graph['inputs']
    for node in graph['nodes']:
        if node['op'] == 'relu':
            scale = scales[node['input']]
        else:
            scale = Fraction(node['bias']).denominator
            for ref, weight in node['terms']:
                scale = math.lcm(scale, (Fraction(weight) / scales[ref]).denominator)
                if scale > LIMIT:
                    raise OverflowError('Exact static scale exceeds int64 budget')
        if scale > LIMIT:
            raise OverflowError('Exact static scale exceeds int64 budget')
        scales.append(scale)
    def integer(raw):
        q = Fraction(raw)
        if q.denominator != 1 or not -LIMIT <= q <= LIMIT:
            raise ValueError('Edge backend requires representable scaled int64 constants')
        return int(q)
    def safe(lo, hi):
        if not -LIMIT <= lo <= hi <= LIMIT:
            raise OverflowError('Potential int64 overflow')
    raw_bounds = [(math.ceil(lo * scale), math.floor(hi * scale)) for (lo, hi), scale in zip(values, scales)]
    for lo, hi in raw_bounds:
        safe(lo, hi)
    lines = ['#include <stdint.h>',
             '/* Exact scaled rational affine/ReLU graph; see scales.json. */',
             'int omega_edge(const int64_t *input, int64_t *output) {',
             '  if (!input || !output) return -1;']
    for i, (lo, hi) in enumerate(raw_bounds[:graph['inputs']]):
        lines += [f'  if (input[{i}] < ({integer(lo)}LL) || input[{i}] > ({integer(hi)}LL)) return -2;',
                  f'  const int64_t x{i} = input[{i}];']
    for i, node in enumerate(graph['nodes'], graph['inputs']):
        if node['op'] == 'relu':
            lines.append(f'  const int64_t x{i} = x{node["input"]} > 0 ? x{node["input"]} : 0;')
        else:
            bias = integer(Fraction(node['bias']) * scales[i])
            lo = hi = bias
            lines.append(f'  int64_t x{i} = {bias}LL;')
            for ref, raw in node['terms']:
                w = integer(Fraction(raw) * scales[i] / scales[ref])
                a, b = raw_bounds[ref]
                p, q = min(w*a, w*b), max(w*a, w*b)
                safe(p, q)
                lo, hi = lo + p, hi + q
                safe(lo, hi)
                lines.append(f'  x{i} += ({w}LL) * x{ref};')
    lines += [f'  output[{i}] = x{ref};' for i, ref in enumerate(graph['outputs'])]
    lines += ['  return 0;', '}']
    proof, admission = certify_bounds(graph, input_bounds, output_bounds)
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    (root / 'model.c').write_text('\n'.join(lines) + '\n')
    (root / 'bounds.lean').write_text(proof)
    metadata = {'input_scales': scales[:graph['inputs']],
                'output_scales': [scales[i] for i in graph['outputs']], 'node_scales': scales}
    (root / 'scales.json').write_text(json.dumps(metadata, sort_keys=True, indent=2) + '\n')
    return {'source': str(root / 'model.c'), 'admission': admission,
            **metadata, 'heap_bytes': 0,
            'scope': 'exact rational values on declared input grid; statically scaled int64; no rounding'}
