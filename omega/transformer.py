"""Static, bounded PyTorch adapters for certified transformer operations."""
import copy
from dataclasses import dataclass
from fractions import Fraction as Q
from math import prod, sqrt
import operator

import torch
from torch import nn
from torch.nn import functional as F
from torch.fx import Tracer, GraphModule

from .certified_graph import validate


class CertifiedSelfAttention(nn.Module):
    def __init__(self, embed_dim, num_heads=1, *, max_sequence_length=16, causal=False, bias=True):
        super().__init__()
        if (type(embed_dim) is not int or not 1 <= embed_dim <= 64 or type(num_heads) is not int
                or num_heads < 1 or embed_dim % num_heads or type(max_sequence_length) is not int
                or not 1 <= max_sequence_length <= 32 or type(causal) is not bool):
            raise ValueError('Bounded static attention dimensions required')
        self.embed_dim, self.num_heads = embed_dim, num_heads
        self.max_sequence_length, self.causal = max_sequence_length, causal
        self.q_proj = nn.Linear(embed_dim, embed_dim, bias=bias)
        self.k_proj = nn.Linear(embed_dim, embed_dim, bias=bias)
        self.v_proj = nn.Linear(embed_dim, embed_dim, bias=bias)
        self.out_proj = nn.Linear(embed_dim, embed_dim, bias=bias)

    def forward(self, x):
        if x.ndim not in (2,3) or x.shape[-1] != self.embed_dim or not 1 <= x.shape[-2] <= self.max_sequence_length:
            raise ValueError('Attention input must be [sequence, embedding] or [batch, sequence, embedding] within the declared maximum')
        n, d = x.shape[-2], self.embed_dim // self.num_heads
        leading=tuple(x.shape[:-2])
        q, k, v = [layer(x).reshape(*leading,n, self.num_heads, d).transpose(-3, -2)
                   for layer in (self.q_proj, self.k_proj, self.v_proj)]
        scores = (q @ k.transpose(-1, -2)) / sqrt(d)
        if self.causal:
            scores = scores.masked_fill(torch.ones(n, n, dtype=torch.bool, device=x.device).triu(1), float('-inf'))
        return self.out_proj((scores.softmax(-1) @ v).transpose(-3, -2).reshape(*leading,n, self.embed_dim))


class CertifiedSwiGLU(nn.Module):
    def __init__(self, in_features, hidden_features, out_features=None, *, bias=True):
        super().__init__()
        self.gate = nn.Linear(in_features, hidden_features, bias=bias)
        self.value = nn.Linear(in_features, hidden_features, bias=bias)
        self.out = nn.Linear(hidden_features, out_features or in_features, bias=bias)

    def forward(self, x):
        return self.out(torch.nn.functional.silu(self.gate(x)) * self.value(x))


@dataclass(frozen=True)
class TensorRefs:
    flat: tuple
    shape: tuple


class Builder:
    def __init__(self, shape):
        self.graph = {'inputs': prod(shape), 'nodes': [], 'outputs': []}
        self.input = TensorRefs(tuple(range(prod(shape))), tuple(shape))

    def emit(self, op, **fields):
        if len(self.graph['nodes']) >= 4096:
            raise ValueError('Static graph node budget exceeded')
        ref = self.graph['inputs'] + len(self.graph['nodes'])
        self.graph['nodes'].append({'op': op, **fields})
        return ref

    def affine(self, terms=(), bias=0):
        return self.emit('affine', terms=[[r, str(Q(w))] for r, w in terms], bias=str(Q(bias)))

    def linear(self, x, weight, bias=None):
        rows, cols = weight.shape
        if x.shape[-1] != cols:
            raise ValueError('Static linear shape mismatch')
        out = []
        for start in range(0, len(x.flat), cols):
            for i in range(rows):
                terms = [(x.flat[start+j], Q(float(weight[i, j].detach()))) for j in range(cols)]
                out.append(self.affine(terms, Q(float(bias[i].detach())) if bias is not None else 0))
        return TensorRefs(tuple(out), x.shape[:-1] + (rows,))

    def relu(self, x):
        return TensorRefs(tuple(self.emit('relu', input=r) for r in x.flat), x.shape)

    def softmax_group(self, refs):
        # A fixed zero shift preserves softmax exactly and is independent of the
        # input. The certified exp domain bounds the accepted logit magnitudes.
        exponentials = [self.emit('exp', input=r) for r in refs]
        denominator = self.affine([(r, 1) for r in exponentials])
        return [self.emit('div', left=r, right=denominator) for r in exponentials]

    def softmax(self, x, dim):
        if dim not in (-1, len(x.shape)-1):
            raise ValueError('Certified softmax normalizes the last dimension')
        width = x.shape[-1]
        refs = []
        for start in range(0, len(x.flat), width):
            refs += self.softmax_group(x.flat[start:start+width])
        return TensorRefs(tuple(refs), x.shape)

    def rmsnorm(self, x, layer, dtype):
        if tuple(layer.normalized_shape) != (x.shape[-1],):
            raise ValueError('RMSNorm requires one fixed final dimension')
        eps = Q(float(layer.eps if layer.eps is not None else torch.finfo(dtype).eps))
        if eps <= 0:
            raise ValueError('RMSNorm epsilon must be strictly positive')
        width = x.shape[-1]
        result = []
        for start in range(0, len(x.flat), width):
            block = x.flat[start:start+width]
            squares = [self.emit('square', input=r) for r in block]
            mean = self.affine([(r, Q(1, width)) for r in squares], eps)
            inv = self.emit('rsqrt', input=mean)
            for j, ref in enumerate(block):
                normalized = self.emit('mul', left=ref, right=inv)
                weight = Q(float(layer.weight[j].detach())) if layer.weight is not None else Q(1)
                result.append(self.affine([(normalized, weight)]))
        return TensorRefs(tuple(result), x.shape)

    def silu(self, x):
        result = []
        for r in x.flat:
            negative = self.affine([(r, -1)])
            exp = self.emit('exp', input=negative)
            denominator = self.affine([(exp, 1)], 1)
            result.append(self.emit('div', left=r, right=denominator))
        return TensorRefs(tuple(result), x.shape)

    def elementwise(self, a, b, op):
        if a.shape != b.shape:
            raise ValueError('Elementwise shapes must match; implicit broadcasting is refused')
        refs = [self.emit('mul', left=l, right=r) if op == 'mul' else self.affine([(l, 1), (r, 1)])
                for l, r in zip(a.flat, b.flat)]
        return TensorRefs(tuple(refs), a.shape)

    def attention(self, x, layer, *, causal=None):
        if len(x.shape)==3:
            if type(layer) is nn.MultiheadAttention and not layer.batch_first:
                raise ValueError('Batched MHA export requires batch_first=True')
            batch,n,embed=x.shape;output=[]
            for b in range(batch):
                block=TensorRefs(x.flat[b*n*embed:(b+1)*n*embed],(n,embed))
                output.extend(self.attention(block,layer,causal=causal).flat)
            return TensorRefs(tuple(output),x.shape)
        n, embed = x.shape if len(x.shape) == 2 else (0, 0)
        if not n or embed != layer.embed_dim:
            raise ValueError('Self-attention requires a static [sequence, embedding] input')
        if isinstance(layer, CertifiedSelfAttention):
            if n > layer.max_sequence_length:
                raise ValueError('Sequence exceeds declared maximum')
            q, k, v = [self.linear(x, p.weight, p.bias) for p in (layer.q_proj, layer.k_proj, layer.v_proj)]
            is_causal = layer.causal
        else:
            if layer.bias_k is not None or layer.bias_v is not None or layer.add_zero_attn or layer.in_proj_weight is None:
                raise ValueError('Unsupported MultiheadAttention projection layout')
            weights = layer.in_proj_weight.chunk(3)
            biases = layer.in_proj_bias.chunk(3) if layer.in_proj_bias is not None else (None,)*3
            q, k, v = [self.linear(x, w, b) for w, b in zip(weights, biases)]
            is_causal = bool(causal)
        heads = layer.num_heads
        width = embed // heads
        dimension = self.affine(bias=width)
        scale = self.emit('rsqrt', input=dimension)
        out = [None] * (n * embed)
        for h in range(heads):
            for row in range(n):
                keys = list(range(row+1 if is_causal else n))
                scores = []
                for col in keys:
                    products = [self.emit('mul', left=q.flat[row*embed+h*width+j], right=k.flat[col*embed+h*width+j]) for j in range(width)]
                    dot = self.affine([(r, 1) for r in products])
                    scores.append(self.emit('mul', left=dot, right=scale))
                probabilities = self.softmax_group(scores)
                for j in range(width):
                    products = [self.emit('mul', left=p, right=v.flat[col*embed+h*width+j]) for col, p in zip(keys, probabilities)]
                    out[row*embed+h*width+j] = self.affine([(r, 1) for r in products])
        merged = TensorRefs(tuple(out), x.shape)
        return self.linear(merged, layer.out_proj.weight, layer.out_proj.bias)


def trace_model(model, example_inputs):
    if (not isinstance(example_inputs, torch.Tensor) or not 1 <= example_inputs.ndim <= 3
            or not example_inputs.is_floating_point() or not 1 <= example_inputs.numel() <= 256
            or any(d < 1 for d in example_inputs.shape)):
        raise ValueError('A nonempty static floating tensor of rank 1..3 and at most 256 coordinates is required')
    frozen = copy.deepcopy(model).cpu().eval()
    leaf_types = (nn.Linear, nn.ReLU, nn.Softmax, nn.RMSNorm, nn.SiLU, nn.Identity, nn.Dropout,
                  nn.MultiheadAttention, CertifiedSelfAttention, CertifiedSwiGLU)
    class StaticTracer(Tracer):
        def is_leaf_module(self, module, name):
            return type(module) in leaf_types or super().is_leaf_module(module, name)
    class Root(nn.Module):
        def __init__(self, child):
            super().__init__()
            self.model = child
        def forward(self, x):
            return self.model(x)
    root = Root(frozen)
    tracer = StaticTracer()
    try:
        traced = GraphModule(root, tracer.trace(root))
    except torch.fx.proxy.TraceError as exc:
        raise ValueError('Value-dependent Python control flow cannot be statically certified') from exc
    builder = Builder(tuple(example_inputs.shape))
    refs = {}
    output = None
    for node in traced.graph.nodes:
        if node.op == 'placeholder':
            refs[node] = builder.input
        elif node.op == 'call_module':
            layer = traced.get_submodule(node.target)
            if not node.args or node.args[0] not in refs:
                raise ValueError('Unsupported module arguments')
            x = refs[node.args[0]]
            if type(layer) is nn.MultiheadAttention:
                if len(node.args) != 3 or not all(arg is node.args[0] for arg in node.args) or any(k not in ('need_weights', 'is_causal') for k in node.kwargs):
                    raise ValueError('Only unmasked self-attention Q=K=V is supported by the MHA adapter; use CertifiedSelfAttention for causal masks')
                if node.kwargs.get('need_weights', True):
                    raise ValueError('Set need_weights=False for certified MHA export')
                refs[node] = (builder.attention(x, layer, causal=node.kwargs.get('is_causal', False)), None)
            elif type(layer) is nn.Linear:
                refs[node] = builder.linear(x, layer.weight, layer.bias)
            elif type(layer) is nn.ReLU and not layer.inplace:
                refs[node] = builder.relu(x)
            elif type(layer) is nn.Softmax:
                refs[node] = builder.softmax(x, layer.dim)
            elif type(layer) is nn.RMSNorm:
                refs[node] = builder.rmsnorm(x, layer, example_inputs.dtype)
            elif type(layer) is nn.SiLU and not layer.inplace:
                refs[node] = builder.silu(x)
            elif type(layer) in (nn.Identity,nn.Dropout) and not layer.training:
                refs[node] = x
            elif type(layer) is CertifiedSelfAttention:
                refs[node] = builder.attention(x, layer)
            elif type(layer) is CertifiedSwiGLU:
                gate = builder.linear(x, layer.gate.weight, layer.gate.bias)
                value = builder.linear(x, layer.value.weight, layer.value.bias)
                inner = builder.elementwise(builder.silu(gate), value, 'mul')
                refs[node] = builder.linear(inner, layer.out.weight, layer.out.bias)
            else:
                raise ValueError(f'Unsupported module: {type(layer).__name__}')
        elif node.op == 'call_function' and node.target is operator.getitem:
            parent, index = node.args
            if parent not in refs or type(refs[parent]) is not tuple or type(index) is not int:
                raise ValueError('Only explicit attention tuple selection is supported')
            refs[node] = refs[parent][index]
        elif node.op == 'call_function' and node.target in (operator.add, operator.mul, torch.add, torch.mul):
            if len(node.args) != 2 or node.kwargs or any(arg not in refs for arg in node.args):
                raise ValueError('Static tensor operands required')
            refs[node] = builder.elementwise(refs[node.args[0]], refs[node.args[1]], 'add' if node.target in (operator.add, torch.add) else 'mul')
        elif node.op == 'call_function' and node.target in (torch.softmax,F.softmax,torch.relu,F.relu,F.silu):
            if not node.args or node.args[0] not in refs:
                raise ValueError('Static activation input required')
            x=refs[node.args[0]]
            if node.target in (torch.softmax,F.softmax):
                dim=node.kwargs.get('dim',node.args[1] if len(node.args)>1 else None)
                if node.kwargs.get('dtype') is not None:
                    raise ValueError('Explicit activation dtype conversions are unsupported')
                refs[node]=builder.softmax(x,dim)
            else:
                if node.kwargs.get('inplace',node.args[1] if len(node.args)>1 else False):
                    raise ValueError('In-place activations are unsupported')
                refs[node]=builder.silu(x) if node.target is F.silu else builder.relu(x)
        elif node.op == 'output':
            if len(node.args) != 1 or node.args[0] not in refs or not isinstance(refs[node.args[0]], TensorRefs):
                raise ValueError('Exactly one static tensor output is required')
            output = refs[node.args[0]]
        else:
            raise ValueError(f'Unsupported FX operation: {node.op}/{node.target}')
    if output is None:
        raise ValueError('Graph has no tensor output')
    builder.graph['outputs'] = list(output.flat)
    if example_inputs.ndim != 1:
        builder.graph['input_shape'] = list(example_inputs.shape)
        builder.graph['output_shape'] = list(output.shape)
    return validate(builder.graph)
