"""Signed proof-carrying inference; keys and expected identities are external.

An Ed25519 signature authenticates an issuer, not mathematical correctness.
Verification reruns the Lean checks; there is no succinct/microsecond claim.
"""
from fractions import Fraction
import hashlib
from .certified_graph import validate, evaluate, bounds_contract, certify_bounds, _q
from omega_selfhost.proof_protocol import encode

FORMAT = 'omega-pci-1'


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def _statement(graph, inputs, input_bounds, output_bounds):
    # Freeze caller-owned structures before any checking or signing.
    import json
    graph = json.loads(encode(validate(graph)))
    bounds = bounds_contract(input_bounds, graph['inputs'])
    outputs = bounds_contract(output_bounds, len(graph['outputs']))
    if len(inputs) != len(bounds):
        raise ValueError('Input shape mismatch')
    exact = [_q(x) for x in inputs]
    if any(not lo <= x <= hi for x, (lo, hi) in zip(exact, bounds)):
        raise ValueError('Input outside certified domain')
    return {'graph': graph, 'graph_sha256': digest(graph), 'inputs': list(map(str, exact)),
            'outputs': list(map(str, evaluate(graph, exact))),
            'input_bounds': [[str(a), str(b)] for a, b in bounds],
            'output_bounds': [[str(a), str(b)] for a, b in outputs]}


def issue(graph, inputs, *, input_bounds, output_bounds, signing_key, nonce, context):
    """Caller supplies a private-key object; no implicit keys or trust anchors."""
    if type(nonce) is not str or not 1 <= len(nonce) <= 256 or type(context) is not str or not 1 <= len(context) <= 256:
        raise ValueError('Bounded nonce and deployment context required')
    from .certified_graph import real_operations
    if real_operations(graph):
        raise ValueError('Real graphs require issue_real with an explicit error contract')
    statement = _statement(graph, inputs, input_bounds, output_bounds)
    source, admission = certify_bounds(statement['graph'], statement['input_bounds'], statement['output_bounds'])
    # Concrete execution equality is independently rendered and kernel checked.
    from .certified_proof import check, rational_literal as lit
    from .certified_graph import expression
    values = [lit(x) for x in statement['inputs']]
    lines = ['import ProofPrelude', 'namespace OmegaInference', 'theorem execution :']
    for node in statement['graph']['nodes']:
        name = f'v{len(values)}'
        lines.append(f'  let {name} : ℚ := {expression(node, values)};')
        values.append(name)
    goals = [f'({values[ref]} = {lit(y)})' for ref, y in zip(statement['graph']['outputs'], statement['outputs'])]
    lines += ['  ' + ' ∧ '.join(goals) + ' := by norm_num', '#print axioms execution', 'end OmegaInference']
    execution = '\n'.join(lines) + '\n'
    evidence = check(execution, ['OmegaInference.execution'])
    payload = {'format': FORMAT, 'statement': statement, 'nonce': nonce, 'context': context,
               'proof_sha256': hashlib.sha256(source.encode()).hexdigest(),
               'execution_sha256': hashlib.sha256(execution.encode()).hexdigest()}
    signature = signing_key.sign(encode(payload))
    return {'payload': payload, 'signature': signature.hex(),
            'proof': source, 'execution_proof': execution,
            'admission': {'bounds': admission, 'execution': evidence}}


def verify(certificate, *, public_key, expected_graph_sha256, expected_inputs,
           expected_nonce, expected_context, expected_input_bounds, expected_output_bounds,
           expected_max_error=None):
    """Authenticate and recheck against caller-pinned model, input and request."""
    if type(certificate) is dict and type(certificate.get('payload')) is dict and certificate['payload'].get('format') == 'omega-pci-real-1':
        from .transformer_certificate import verify_real
        return verify_real(certificate, public_key=public_key, expected_graph_sha256=expected_graph_sha256,
                           expected_inputs=expected_inputs, expected_nonce=expected_nonce, expected_context=expected_context,
                           expected_input_bounds=expected_input_bounds, expected_output_bounds=expected_output_bounds,
                           expected_max_error=expected_max_error)
    if type(certificate) is not dict or set(certificate) != {
            'payload', 'signature', 'proof', 'execution_proof', 'admission'}:
        raise ValueError('Unknown PCI envelope')
    payload = certificate['payload']
    if type(payload) is not dict or set(payload) != {
            'format', 'statement', 'nonce', 'context', 'proof_sha256', 'execution_sha256'}:
        raise ValueError('Unknown PCI payload')
    if payload['format'] != FORMAT or payload['nonce'] != expected_nonce or payload['context'] != expected_context:
        raise ValueError('Unrelated inference request')
    public_key.verify(bytes.fromhex(certificate['signature']), encode(payload))
    statement = payload['statement']
    if statement['graph_sha256'] != expected_graph_sha256 or statement['inputs'] != list(map(lambda x: str(Fraction(x)), expected_inputs)):
        raise ValueError('Unrelated model or input')
    wanted_inputs = [[str(a), str(b)] for a, b in bounds_contract(expected_input_bounds, statement['graph']['inputs'])]
    wanted_outputs = [[str(a), str(b)] for a, b in bounds_contract(expected_output_bounds, len(statement['graph']['outputs']))]
    if statement['input_bounds'] != wanted_inputs or statement['output_bounds'] != wanted_outputs:
        raise ValueError('Unrelated operational contract')
    rebuilt = _statement(statement['graph'], statement['inputs'], statement['input_bounds'], statement['output_bounds'])
    if encode(rebuilt) != encode(statement):
        raise ValueError('Changed inference statement')
    # Reconstruct every proof; never execute the supplied Lean source.
    class Capture:
        def sign(self, raw):
            if raw != encode(payload):
                raise ValueError('Proof binding mismatch')
            return bytes.fromhex(certificate['signature'])
    replay = issue(statement['graph'], statement['inputs'], input_bounds=statement['input_bounds'],
                   output_bounds=statement['output_bounds'], signing_key=Capture(),
                   nonce=expected_nonce, context=expected_context)
    if any(replay[k] != certificate[k] for k in ('proof', 'execution_proof')):
        raise ValueError('Changed proof artifact')
    return {'valid': True, 'outputs': rebuilt['outputs'], 'graph_sha256': expected_graph_sha256}


def verify_export(directory, *, public_key, **expected):
    """Check the signed build bundle and its PCI against an external trust anchor."""
    from pathlib import Path
    import json
    import stat
    from omega.typed_ir import _pairs
    root = Path(directory)
    def read(name, limit):
        path = root / name
        if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > limit:
            raise ValueError('Bounded regular artifact required')
        return path.read_bytes()
    bundle = json.loads(read('certificate.json', 8 * 1024**2), object_pairs_hook=_pairs)
    if type(bundle) is not dict or set(bundle) != {'pci', 'artifacts', 'artifact_signature'}:
        raise ValueError('Unknown export bundle')
    required={'model.omega','model.c','model'}
    if type(bundle['artifacts']) is not dict or not required <= set(bundle['artifacts']) <= required | {'model.build.json'}:
        raise ValueError('Unknown artifact membership')
    binding = {'pci_sha256': digest(bundle['pci']), 'artifacts': bundle['artifacts']}
    public_key.verify(bytes.fromhex(bundle['artifact_signature']), encode(binding))
    for name, expected_hash in bundle['artifacts'].items():
        if hashlib.sha256(read(name, 64 * 1024**2)).hexdigest() != expected_hash:
            raise ValueError('Changed build artifact: ' + name)
    return verify(bundle['pci'], public_key=public_key, **expected)
