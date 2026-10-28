"""Explicit opt-in PyTorch FX -> exact rational Omega -> GMP + Lean export."""
import copy
from fractions import Fraction
import json
from pathlib import Path

from .certified_graph import evaluate, omega_source, validate
from .pci import issue


def trace(model, example_inputs):
    import torch
    from torch.fx import symbolic_trace
    if not isinstance(example_inputs, torch.Tensor) or example_inputs.ndim != 1 or not 1 <= example_inputs.numel() <= 256:
        raise ValueError('One static 1D tensor input required')
    frozen = copy.deepcopy(model).cpu().eval()
    traced = symbolic_trace(frozen)
    graph = {'inputs': example_inputs.numel(), 'nodes': [], 'outputs': []}
    refs = {}
    for node in traced.graph.nodes:
        if node.op == 'placeholder':
            if refs:
                raise ValueError('Exactly one model input supported')
            refs[node] = list(range(graph['inputs']))
        elif node.op == 'call_module':
            if len(node.args) != 1 or node.kwargs or node.args[0] not in refs:
                raise ValueError('Only unary static module calls supported')
            source = refs[node.args[0]]
            layer = traced.get_submodule(node.target)
            out = []
            if type(layer) is torch.nn.Linear:
                if len(source) != layer.in_features:
                    raise ValueError('Linear input shape mismatch')
                for i in range(layer.out_features):
                    bias = Fraction(float(layer.bias[i].detach())) if layer.bias is not None else Fraction(0)
                    terms = [[r, str(Fraction(float(layer.weight[i, j].detach())))] for j, r in enumerate(source)]
                    out.append(graph['inputs'] + len(graph['nodes']))
                    graph['nodes'].append({'op': 'affine', 'terms': terms, 'bias': str(bias)})
            elif type(layer) is torch.nn.ReLU and not layer.inplace:
                for ref in source:
                    out.append(graph['inputs'] + len(graph['nodes']))
                    graph['nodes'].append({'op': 'relu', 'input': ref})
            else:
                raise ValueError(f'Unsupported module: {type(layer).__name__}')
            refs[node] = out
        elif node.op == 'output':
            if len(node.args) != 1 or node.args[0] not in refs:
                raise ValueError('One tensor output required')
            graph['outputs'] = refs[node.args[0]]
        else:
            raise ValueError(f'Unsupported FX operation: {node.op}/{node.target}')
        if len(graph['nodes']) > 4096:
            raise ValueError('Static graph node budget exceeded')
    return validate(graph)


def export(model, example_inputs, directory, *, input_bounds, output_bounds,
           signing_key, nonce, static=True, target='critical-system'):
    graph = trace(model, example_inputs)
    inputs = [Fraction(float(x)) for x in example_inputs.detach().cpu()]
    certificate = issue(graph, inputs, input_bounds=input_bounds, output_bounds=output_bounds,
                        signing_key=signing_key, nonce=nonce, context=target)
    root = Path(directory).absolute()
    root.mkdir(parents=True, exist_ok=False)
    source = root / 'model.omega'
    source.write_text(omega_source(graph, inputs))
    from omega_selfhost.driver import build, run
    binary = root / 'model'
    build(source, binary, static=static)
    result, admission = run(binary)
    # Native outputs have the same order as mostrar statements.
    expected = [str(x) for x in evaluate(graph, inputs)]
    observed = [str(Fraction(result['values'][f'x{ref}'])) for ref in graph['outputs']]
    if observed != expected:
        raise ValueError('Native execution disagrees with exact FX graph')
    import hashlib
    artifacts = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                for name in ('model.omega', 'model.c', 'model')}
    # Artifact provenance is separately signed; core PCI remains independently portable.
    from omega_selfhost.proof_protocol import encode
    bundle = {'pci': certificate, 'artifacts': artifacts,
              'artifact_signature': signing_key.sign(encode({'pci_sha256': hashlib.sha256(encode(certificate)).hexdigest(),
                                                           'artifacts': artifacts})).hex()}
    (root / 'bounds.lean').write_text(certificate['proof'])
    (root / 'execution.lean').write_text(certificate['execution_proof'])
    (root / 'certificate.json').write_text(json.dumps(bundle, sort_keys=True, indent=2) + '\n')
    (root / 'native-result.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    return {'directory': str(root), 'outputs': expected, 'native_admission': admission,
            'certificate': certificate, 'static': static,
            'scope': 'exact reinterpretation of frozen float weights; this input binary; universal box bounds'}


def certify(*, target='critical-system', precision='exact-rational'):
    if precision != 'exact-rational' or type(target) is not str or not target:
        raise ValueError('A named target and exact-rational precision are required')
    def decorate(cls):
        if hasattr(cls, 'export_certified'):
            raise ValueError('export_certified already exists')
        def export_certified(self, example_inputs, directory, **kwargs):
            return export(self, example_inputs, directory, target=target, **kwargs)
        cls.export_certified = export_certified
        return cls
    return decorate
