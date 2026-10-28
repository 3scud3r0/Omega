"""Signed real-semantics contracts and native rational transformer exports."""
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path

from .certified_graph import validate, bounds_contract, _q
from .real_graph import certify
from .pci import digest
from omega_selfhost.proof_protocol import encode

FORMAT = 'omega-pci-real-1'


def _prepare(graph, inputs, input_bounds, output_bounds, max_error, nonce, context):
    if type(nonce) is not str or not 1 <= len(nonce) <= 256 or type(context) is not str or not 1 <= len(context) <= 256:
        raise ValueError('Bounded deployment context and request nonce required')
    graph = json.loads(encode(validate(graph)))
    inputs = list(map(lambda x: str(_q(x)), inputs))
    domain = [[str(a), str(b)] for a, b in bounds_contract(input_bounds, graph['inputs'])]
    output = [[str(a), str(b)] for a, b in bounds_contract(output_bounds, len(graph['outputs']))]
    checked = certify(graph, inputs, domain, output, max_error)
    statement = {'graph': graph, 'graph_sha256': digest(graph), 'inputs': inputs,
                 'input_bounds': domain, 'output_bounds': output,
                 'outputs': checked['outputs'], 'max_error': checked['max_error'],
                 'error_bounds': checked['error_bounds']}
    payload = {'format': FORMAT, 'statement': statement, 'nonce': nonce, 'context': context,
               'proof_sha256': hashlib.sha256(checked['proof'].encode()).hexdigest()}
    return payload, checked


def issue_real(graph, inputs, *, input_bounds, output_bounds, max_error, signing_key, nonce, context):
    payload, checked = _prepare(graph, inputs, input_bounds, output_bounds, max_error, nonce, context)
    return {'payload': payload, 'proof': checked['proof'], 'admission': checked['admission'],
            'signature': signing_key.sign(encode(payload)).hex()}


def verify_real(certificate, *, public_key, expected_graph_sha256, expected_inputs,
                expected_input_bounds, expected_output_bounds, expected_max_error,
                expected_nonce, expected_context):
    if type(certificate) is not dict or set(certificate) != {'payload', 'proof', 'admission', 'signature'}:
        raise ValueError('Unknown real PCI envelope')
    payload = certificate['payload']
    if type(payload) is not dict or set(payload) != {'format', 'statement', 'nonce', 'context', 'proof_sha256'}:
        raise ValueError('Unknown real PCI payload')
    public_key.verify(bytes.fromhex(certificate['signature']), encode(payload))
    if payload['format'] != FORMAT or payload['nonce'] != expected_nonce or payload['context'] != expected_context:
        raise ValueError('Unrelated real inference request')
    statement = payload['statement']
    if statement['graph_sha256'] != expected_graph_sha256 or statement['inputs'] != [str(_q(x)) for x in expected_inputs]:
        raise ValueError('Unrelated model or inputs')
    if expected_max_error is None:
        raise ValueError('Auditor must pin the approximation error contract')
    count=len(statement['graph']['outputs'])
    errors=[str(_q(expected_max_error))]*count if type(expected_max_error) in (str,int,Q) else [str(_q(x)) for x in expected_max_error]
    domain=[[str(a),str(b)] for a,b in bounds_contract(expected_input_bounds,statement['graph']['inputs'])]
    output=[[str(a),str(b)] for a,b in bounds_contract(expected_output_bounds,count)]
    if statement['max_error']!=errors or statement['input_bounds']!=domain or statement['output_bounds']!=output:
        raise ValueError('Unrelated real operational contract')
    if hashlib.sha256(certificate['proof'].encode()).hexdigest()!=payload['proof_sha256']:
        raise ValueError('Changed real proof artifact')
    replay, checked = _prepare(statement['graph'], expected_inputs, expected_input_bounds,
                               expected_output_bounds, expected_max_error, expected_nonce, expected_context)
    if encode(replay) != encode(payload) or checked['proof'] != certificate['proof']:
        raise ValueError('Changed real statement, contract or proof')
    return {'valid': True, 'outputs': statement['outputs'], 'error_bounds': statement['error_bounds'],
            'graph_sha256': expected_graph_sha256, 'semantics': 'real graph with bounded rational output error'}


def export_real(graph, inputs, directory, *, input_bounds, output_bounds, max_error,
                signing_key, nonce, static=True, target='critical-system'):
    certificate = issue_real(graph, inputs, input_bounds=input_bounds, output_bounds=output_bounds,
                             max_error=max_error, signing_key=signing_key, nonce=nonce, context=target)
    root = Path(directory).absolute()
    root.mkdir(parents=True, exist_ok=False)
    from .real_native import build_runtime,run_runtime
    build_runtime(graph,root,input_bounds,static=static)
    actual,native_admission=run_runtime(graph,root/'model',inputs)
    expected = certificate['payload']['statement']['outputs']
    if actual != expected:
        raise ValueError('Native rational execution disagrees with the certified output')
    artifacts = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ('model.omega', 'model.c', 'model', 'model.build.json')}
    binding = {'pci_sha256': digest(certificate), 'artifacts': artifacts}
    bundle = {'pci': certificate, 'artifacts': artifacts, 'artifact_signature': signing_key.sign(encode(binding)).hex()}
    (root / 'certificate.json').write_text(json.dumps(bundle, sort_keys=True, indent=2) + '\n')
    (root / 'real-error.lean').write_text(certificate['proof'])
    (root / 'native-result.json').write_text(json.dumps({'outputs':actual,'admission':native_admission}, sort_keys=True, indent=2) + '\n')
    return {'directory': str(root), 'outputs': expected,
            'error_bounds': certificate['payload']['statement']['error_bounds'],
            'certificate': certificate, 'native_admission': native_admission, 'static': static,
            'scope': 'real graph domain bounds and concrete rational error; reusable native binary for this fixed shape and input domain'}
