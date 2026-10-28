"""Explicit opt-in PyTorch FX -> exact rational Omega -> GMP + Lean export."""
import copy
from fractions import Fraction
import json
from pathlib import Path

from .certified_graph import evaluate, omega_source, validate
from .pci import issue


def trace(model, example_inputs):
    from .transformer import trace_model
    return trace_model(model, example_inputs)


def export(model, example_inputs, directory, *, input_bounds, output_bounds,
           signing_key, nonce, static=True, target='critical-system', max_error=None,
           precision_bits=32):
    graph = trace(model, example_inputs)
    inputs = [Fraction(float(x)) for x in example_inputs.detach().cpu().reshape(-1)]
    from .certified_graph import real_operations
    if real_operations(graph):
        from .transformer_certificate import export_real
        if max_error is None:
            raise ValueError('Real operations require an explicit max_error contract')
        graph['precision_bits'] = precision_bits
        return export_real(graph, inputs, directory, input_bounds=input_bounds,
                           output_bounds=output_bounds, signing_key=signing_key, nonce=nonce,
                           static=static, target=target, max_error=max_error)
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
    if precision not in ('exact-rational', 'certified-rational') or type(target) is not str or not target:
        raise ValueError('A named target and an explicit rational precision mode are required')
    def decorate(cls):
        if hasattr(cls, 'export_certified'):
            raise ValueError('export_certified already exists')
        def export_certified(self, example_inputs, directory, **kwargs):
            if precision == 'exact-rational' and kwargs.get('max_error') is not None:
                raise ValueError('Use precision="certified-rational" to permit transcendental approximation')
            return export(self, example_inputs, directory, target=target, **kwargs)
        cls.export_certified = export_certified
        return cls
    return decorate
