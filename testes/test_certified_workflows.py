"""Behavioral and adversarial checks for exact certified workflows."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import subprocess

import pytest

from omega.certified_graph import evaluate, intervals, bound_source, certify_bounds, validate
from omega.rational_pruning import approximate, certify_argmax
from omega.pci import issue, verify, digest


@pytest.fixture
def graph():
    return {'inputs': 2, 'nodes': [
        {'op': 'affine', 'terms': [[0, '2'], [1, '-1']], 'bias': '1'},
        {'op': 'relu', 'input': 2},
        {'op': 'affine', 'terms': [[3, '1/2']], 'bias': '-1'}], 'outputs': [4, 3]}


def test_exact_graph_and_interval_propagation(graph):
    assert evaluate(graph, ['1/3', '1/7']) == [Fraction(-5, 21), Fraction(32, 21)]
    assert intervals(graph, [[-1, 1], [-2, 2]])[-1] == (Fraction(-1), Fraction(3, 2))
    with pytest.raises(ValueError, match='not established'):
        bound_source(graph, [[-1, 1], [-2, 2]], [[-1, 1], [0, 5]])


@pytest.mark.parametrize('bad', [True, 0, -1, 2**128])
def test_denominator_budget_rejected(bad):
    with pytest.raises(ValueError):
        approximate('1/3', max_denominator=bad)


def test_continued_fraction_nearest_and_magnitude_budget():
    value, error = approximate('355/113', max_denominator=100)
    assert value == Fraction(311, 99)
    assert error == abs(Fraction(355, 113) - value)
    assert all(abs(Fraction(355, 113) - Fraction(n, d)) >= error
               for d in range(1, 101) for n in range(3*d, 4*d))
    with pytest.raises(OverflowError):
        approximate(2**129, max_bits=128)


def test_ties_and_insufficient_margin_rejected():
    with pytest.raises(ValueError, match='margin'):
        certify_argmax(['1/3', '1/3'])
    with pytest.raises(ValueError, match='margin'):
        certify_argmax(['1001/3000', '1/3'], max_denominator=1)


@pytest.mark.lean
def test_bounded_intermediates_certify_forward_decision():
    from omega.rational_pruning import certify_bounded_graph
    graph = {'inputs': 1, 'nodes': [
        {'op': 'affine', 'terms': [[0, '1/3']], 'bias': '3'},
        {'op': 'relu', 'input': 1},
        {'op': 'affine', 'terms': [[0, '-1/7']], 'bias': '0'}], 'outputs': [2, 3]}
    result = certify_bounded_graph(graph, ['1/11'], max_denominator=64, max_bits=64)
    assert result['argmax'] == 0
    assert 'OmegaDecision.winner_1' in result['admission']['theorems']
    assert all(Fraction(x).denominator <= 64 for x in result['outputs'])


def test_graph_rejects_forward_references_and_nonfinite(graph):
    graph['nodes'][0]['terms'][0][0] = 999
    with pytest.raises(ValueError):
        validate(graph)


@pytest.mark.lean
def test_lean_bounds_positive_negative_relu_and_pruning(graph):
    source, admission = certify_bounds(graph, [[-1, 1], [-2, 2]], [[-1, '3/2'], [0, 5]])
    assert admission['theorems'] == ['OmegaBounds.bounds']
    assert 'sorry' not in source
    result = certify_argmax(['10001/3000', '1/3'], max_denominator=100)
    assert result['argmax'] == 0
    assert result['admission']['theorems']


@pytest.mark.lean
def test_signed_pci_replay_binding_and_tampering(graph):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.exceptions import InvalidSignature
    key = Ed25519PrivateKey.generate()
    certificate = issue(graph, ['1/3', '1/7'], input_bounds=[[-1, 1], [-2, 2]],
                        output_bounds=[[-1, '3/2'], [0, 5]], signing_key=key,
                        nonce='request-1', context='controller-v1')
    kwargs = dict(public_key=key.public_key(), expected_graph_sha256=digest(graph),
                  expected_inputs=['1/3', '1/7'], expected_nonce='request-1', expected_context='controller-v1',
                  expected_input_bounds=[[-1, 1], [-2, 2]], expected_output_bounds=[[-1, '3/2'], [0, 5]])
    assert verify(certificate, **kwargs)['valid']
    altered = copy.deepcopy(certificate)
    altered['payload']['statement']['outputs'][0] = '999'
    with pytest.raises(InvalidSignature):
        verify(altered, **kwargs)
    with pytest.raises(ValueError, match='Unrelated'):
        verify(certificate, **{**kwargs, 'expected_nonce': 'request-2'})
    with pytest.raises(ValueError, match='contract'):
        verify(certificate, **{**kwargs, 'expected_output_bounds': [[-100, 100], [0, 5]]})
    altered = copy.deepcopy(certificate)
    altered['execution_proof'] += '\n-- changed\n'
    with pytest.raises(ValueError, match='proof artifact'):
        verify(altered, **kwargs)


def test_fx_static_trace_matches_exact_weights_and_rejects_ops():
    import torch
    import omega
    from omega.certify import trace
    @omega.certify(target='test', precision='exact-rational')
    class Network(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.fc = torch.nn.Linear(2, 2)
            self.relu = torch.nn.ReLU()
            with torch.no_grad():
                self.fc.weight.copy_(torch.tensor([[2., -1.], [-1., 1.]]))
                self.fc.bias.copy_(torch.tensor([1., 0.]))
        def forward(self, x):
            return self.relu(self.fc(x))
    model = Network()
    x = torch.tensor([1., 2.])
    graph = trace(model, x)
    assert evaluate(graph, [1, 2]) == [1, 1]
    assert model.training  # Export does not mutate training/evaluation mode.
    with pytest.raises(ValueError, match='1D'):
        trace(model, x.reshape(1, 2))
    class Bad(torch.nn.Module):
        def forward(self, x):
            return torch.sigmoid(x)
    with pytest.raises(ValueError, match='Unsupported FX'):
        trace(Bad(), x)


@pytest.mark.lean
def test_constitutional_transfer_rejects_unsafe_and_stale():
    from omega_agent.constitutional import ResourceState, transfer
    state = ResourceState((5, 1), (10, 4))
    after, evidence = transfer(state, source=0, destination=1, amount=2, expected_version=0)
    assert after.balances == (3, 3) and state.balances == (5, 1)
    assert evidence['admission']['theorems'][-1] == 'OmegaAction.conservation'
    for amount in (4, -1, 0, 6):
        with pytest.raises(ValueError):
            transfer(state, source=0, destination=1, amount=amount, expected_version=0)
    with pytest.raises(ValueError, match='Stale'):
        transfer(after, source=0, destination=1, amount=1, expected_version=0)


@pytest.mark.lean
def test_freestanding_edge_c_matches_exact_and_checks_domain(tmp_path):
    from omega.edge import emit
    graph = {'inputs': 1, 'nodes': [
        {'op': 'affine', 'terms': [[0, '-2']], 'bias': '1'},
        {'op': 'relu', 'input': 1}], 'outputs': [2]}
    output = tmp_path / 'edge'
    emit(graph, [[-3, 3]], [[0, 7]], output)
    harness = output / 'harness.c'
    harness.write_text('#include <stdint.h>\nint omega_edge(const int64_t*,int64_t*);\n'
                       'int main(void){int64_t x,y; for(x=-3;x<=3;x++){if(omega_edge(&x,&y)||y!=(1-2*x>0?1-2*x:0))return 1;} x=4;return omega_edge(&x,&y)==-2?0:2;}\n')
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                    str(output / 'model.c'), str(harness), '-o', str(output / 'check')], check=True)
    subprocess.run([str(output / 'check')], check=True)
    subprocess.run(['cc', '-ffreestanding', '-fno-builtin', '-c', str(output / 'model.c'), '-o', str(output / 'model.o')], check=True)
    assert not subprocess.check_output(['nm', '-u', str(output / 'model.o')]).strip()


@pytest.mark.lean
def test_edge_exact_fractional_scaling_and_intermediate_overflow(tmp_path):
    from omega.edge import emit
    graph = {'inputs': 1, 'nodes': [{'op': 'affine', 'terms': [[0, '1/2']], 'bias': '0'}], 'outputs': [1]}
    result = emit(graph, [[-2, 2]], [[-1, 1]], tmp_path / 'fractional')
    assert result['input_scales'] == [1] and result['output_scales'] == [2]
    harness = tmp_path / 'fractional/harness.c'
    harness.write_text('#include <stdint.h>\nint omega_edge(const int64_t*,int64_t*);\n'
                       'int main(void){int64_t x=1,y;return omega_edge(&x,&y)||y!=1;}\n')
    subprocess.run(['cc', str(tmp_path / 'fractional/model.c'), str(harness), '-o', str(tmp_path / 'fractional/check')], check=True)
    subprocess.run([str(tmp_path / 'fractional/check')], check=True)
    graph['nodes'][0] = {'op': 'affine', 'terms': [[0, str(2**62)], [0, str(-2**62)]], 'bias': '0'}
    with pytest.raises((OverflowError, ValueError)):
        emit(graph, [[2, 2]], [[0, 0]], tmp_path / 'overflow')


@pytest.mark.lean
def test_inverse_distillation_finite_xor(tmp_path):
    from omega_agent.inverse_distillation import distill_boolean
    task = {'id': 'xor', 'arity': 2, 'outputs': [0, 1, 1, 0]}
    result = distill_boolean('Exactly one input is true', task, tmp_path / 'xor', max_size=3)
    assert result['certificate']['checked_rows'] == 4
    assert result['admission']['valid']


@pytest.mark.lean
def test_rule_search_and_two_native_generations(tmp_path):
    from omega_evolution.superoptimization import evolve, audit, discover
    search = discover()
    assert [r['name'] for r in search['rejected']] == ['invalid_drop_addend']
    result = evolve(tmp_path / 'evolution', generations=2)
    assert len(result['generations']) == 2
    assert all(record['fixed_point'] for record in result['generations'])
    assert result['generations'][1]['previous_record'] == result['generations'][0]['sha256']
    assert result['production_promoted'] is False
    head = result['generations'][-1]['sha256']
    assert audit(tmp_path / 'evolution', expected_head_sha256=head)['valid']
    with pytest.raises(ValueError, match='Unrelated'):
        audit(tmp_path / 'evolution', expected_head_sha256='0' * 64)


@pytest.mark.lean
def test_fx_export_static_native_certificate(tmp_path):
    import torch
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from omega.certify import export
    model = torch.nn.Sequential(torch.nn.Linear(2, 2), torch.nn.ReLU())
    with torch.no_grad():
        model[0].weight.copy_(torch.tensor([[2., -1.], [-1., 1.]]))
        model[0].bias.copy_(torch.tensor([1., 0.]))
    key = Ed25519PrivateKey.generate()
    result = export(model, torch.tensor([1., 2.]), tmp_path / 'export',
                    input_bounds=[[0, 2], [0, 2]], output_bounds=[[0, 5], [0, 2]],
                    signing_key=key, nonce='export-1')
    assert result['outputs'] == ['1', '1'] and result['static']
    binary = tmp_path / 'export/model'
    assert 'statically linked' in subprocess.check_output(['file', str(binary)], text=True)
    bundle = json.loads((binary.parent / 'certificate.json').read_text())
    from omega_selfhost.proof_protocol import encode
    import hashlib
    key.public_key().verify(bytes.fromhex(bundle['artifact_signature']),
                            encode({'pci_sha256': hashlib.sha256(encode(bundle['pci'])).hexdigest(),
                                    'artifacts': bundle['artifacts']}))
    from omega.pci import verify_export
    expected = dict(public_key=key.public_key(), expected_graph_sha256=digest(bundle['pci']['payload']['statement']['graph']),
                    expected_inputs=[1, 2], expected_nonce='export-1', expected_context='critical-system',
                    expected_input_bounds=[[0, 2], [0, 2]], expected_output_bounds=[[0, 5], [0, 2]])
    assert verify_export(binary.parent, **expected)['valid']
    binary.write_bytes(binary.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='Changed build artifact'):
        verify_export(binary.parent, **expected)
