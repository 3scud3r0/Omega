import asyncio
from copy import deepcopy
import json
from pathlib import Path
import struct
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from omega_recursive.runtime import ROOT,call
from omega_recursive.certificates import (certify_claim,verify_claim,improvement_certificate,
                                          verify_improvement,arithmetic_cost)
from omega_recursive.cycle import run_cycle,prove_task,activate,self_play
from omega_recursive.gpu import sieve,GPUUnavailable,GPUExecutionError,dispatch
from omega_recursive.swarm import Store,sign,public_key,read_frame,write_frame,handle_peer
from omega_evolution.rollback import Versions


def example(name):
    return json.loads((ROOT/'omega_singularity/examples'/f'{name}.json').read_text())


def claim():
    data = example('sieve')
    return {'format':'omega-epistemic-claim-1','dag':data['programs'][0],'observations':data['observations']}


def test_native_dag_exact_and_topological_validation():
    document = example('sieve')['programs'][0]
    result = call('dag',{'dag':document,'inputs':['1/3'],'lower_i64':1})
    assert result['value'] == '4/3'
    assert result['valid'] == 1
    assert 'funcao hypothesis' in result['source']
    malformed = deepcopy(document)
    malformed['nodes'][0] = ['add',0,[1,1]]
    with pytest.raises(RuntimeError):
        call('dag',{'dag':malformed})


def test_policy_updates_are_bounded_advice():
    result = call('dag',{'mode':'policy-update','weights':[0]*6,'features':[1,0,0,1,0,0],
                       'reward':1,'rate':'1/2'})
    assert result['weights'] == ['1/2',0,0,'1/2',0,0]
    assert result['proof_authority'] == 0


def test_mdl_search_finds_affine_without_holdout_leakage():
    result = call('induce',example('induction'))
    assert result['training_error'] == result['holdout_error'] == 0
    assert result['verified'] == result['universal_optimality_claimed'] == 0
    assert call('dag',{'dag':result['winner'],'inputs':[4]})['value'] == 5
    altered = example('induction')
    altered['holdout'] = [[[0],1]]
    with pytest.raises(RuntimeError,match='overlap'):
        call('induce',altered)


def test_quadratic_search_and_explicit_budget():
    request = {'variables':1,'constants':[-1,0,1,2],'observations':[[[-1],2],[[0],1],[[1],2]],
               'holdout':[[[2],5]],'max_nodes':5,'max_candidates':512,'beam_width':8}
    result = call('induce',request)
    assert result['training_error'] == 0
    assert result['holdout_error'] == 0
    limited = call('induce',dict(request,max_candidates=8))
    assert limited['budget_exhausted'] == 1
    assert limited['search_complete'] == 0
    assert limited['verified'] == 0


def test_finite_mixture_reports_ambiguity():
    result = call('induce',{'variables':1,'constants':[0,1],
                           'observations':[[[0],0]],'max_nodes':3,'max_candidates':128,'predict':[[2]]})
    assert result['consistent_candidates'] > 1
    valid,mean,low,high = result['predictions'][0]
    assert valid == 1 and low < high


@pytest.mark.parametrize('domain',['affine','polynomial','conservative-step'])
def test_synthetic_universes_seed_partition_and_kernel(domain):
    request = {'domain':domain,'seed':41,'tasks':2,'train':3,'heldout':2}
    first = call('universe',request)
    assert first == call('universe',request)
    assert first['external_data_bytes'] == 0
    for task in first['tasks']:
        assert set(tuple(x) for x,y in task['observations']).isdisjoint(tuple(x) for x,y in task['holdout'])
        assert prove_task(task)['verification']['accepted']


def test_point_certificates_reject_wrong_results_and_unrelated_proofs():
    certificate = certify_claim(claim())
    assert verify_claim(certificate)['accepted']
    unrelated = deepcopy(certificate)
    unrelated['packet']['expected'] = unrelated['packet']['proof']
    with pytest.raises(ValueError,match='bound'):
        verify_claim(unrelated)
    forged = claim()
    forged['observations'][0][1] = 99
    assert not verify_claim(certify_claim(forged))['accepted']


def test_rewrite_certificate_checks_coefficients_and_strict_cost():
    proposal = call('improve',{'baseline':example('cycle')['baseline']})
    assert proposal['strict_cost_improvement'] == 1
    assert proposal['applied'] == 0
    assert arithmetic_cost(proposal['candidate']) < arithmetic_cost(proposal['baseline'])
    certificate = improvement_certificate(proposal['baseline'],proposal['candidate'])
    checked = verify_improvement(certificate)
    assert checked['accepted'] and checked['kernel_facts_verified']
    assert not checked['formal_refinement_proved']
    forged = improvement_certificate(proposal['baseline'],example('sieve')['programs'][0])
    assert not verify_improvement(forged)['accepted']
    with pytest.raises(ValueError,match='strict decrease'):
        improvement_certificate(proposal['candidate'],proposal['candidate'])


def test_closed_loop_stops_and_does_not_replace_compiler():
    spec = example('cycle')
    source = ROOT/'omega_selfhost/compiler.omega'
    before = source.read_bytes()
    result = run_cycle(spec['baseline'],spec['observations'],rounds=4)
    assert len(result['generations']) == 1
    assert result['stop_reason'] == 'no-strict-cost-improvement'
    assert not result['stable_version_modified']
    assert source.read_bytes() == before
    for outcomes in result['generations'][0]['executions']:
        assert all(row['sandboxed'] and row['accepted'] for row in outcomes)


def test_stable_activation_has_no_boolean_bypass(tmp_path):
    versions = Versions(tmp_path/'state')
    with pytest.raises(PermissionError):
        activate(versions,'next',{'approved':True,'verified':True},lambda _:True)
    assert versions.current() is None


def test_six_component_self_play_is_finite_and_keeps_stable_state():
    result = self_play({'domain':'affine','seed':42,'rounds':1,'tasks':2})
    assert len(result['records']) == 2
    assert result['verified_claims'] == 2
    assert result['stop_reason'] == 'task-round-budget'
    assert not result['stable_version_modified'] and result['network_actions'] == 0
    assert all(row['sieve']['admitted'][0]['verification']['verified'] for row in result['records'])
    assert any(value != 0 for value in result['advisory_policy'])


def test_cpu_and_gpu_sieve_results_always_return_to_kernel():
    request = example('sieve')
    result = sieve(**request)
    assert result['backend'] == 'cpu'
    assert [item['index'] for item in result['admitted']] == [0]
    assert result['admitted'][0]['verification']['verified']
    with patch('omega_recursive.gpu.dispatch',return_value={'rows':[[0,0,0,0],[0,0,0,0]],'adapter':{}}):
        result = sieve(**request,backend='gpu')
    assert [item['index'] for item in result['admitted']] == [0]
    assert result['rejected'][0]['reason'] == 'GPU/CPU disagreement'
    plan = call('sieve',dict(request,pack_only=1))
    assert plan['cpu_evaluated'] == 0
    assert plan['results'] == plan['fits'] == []
    limited = sieve([request['programs'][0]]*2,request['observations'],max_admitted=1)
    assert len(limited['admitted']) == 1
    assert limited['selection_limited']


def test_gpu_unavailable_fallback_is_explicit():
    with patch('omega_recursive.gpu.dispatch',side_effect=GPUUnavailable('no adapter')):
        result = sieve(**example('sieve'),backend='auto')
        assert result['backend'] == 'cpu'
        assert result['gpu'] is None
        assert 'no adapter' in result['gpu_unavailable_reason']
        with pytest.raises(GPUUnavailable):
            sieve(**example('sieve'),backend='gpu')
    with patch('omega_recursive.gpu.dispatch',side_effect=GPUExecutionError('invalid shader')):
        with pytest.raises(GPUExecutionError):
            sieve(**example('sieve'),backend='auto')


def test_real_webgpu_shader_when_adapter_available():
    plan = call('sieve',example('sieve'))
    try:
        result = dispatch(plan)
    except GPUUnavailable as exc:
        pytest.skip(str(exc))
    assert result['rows'][0][:2] == [0,0]
    assert result['rows'][1][1] == 3


def test_webgpu_rational_operators_and_explicit_intermediate_overflow():
    programs = []
    for op in ['add','sub','mul']:
        programs.append({'format':'omega-symbolic-dag-1','variables':1,
                         'nodes':[['var',0,[]],['const','1/3',[]],[op,0,[0,1]]],'root':2})
    programs.append({'format':'omega-symbolic-dag-1','variables':1,
                     'nodes':[['var',0,[]],['neg',0,[0]]],'root':1})
    spec = {'programs':programs,'observations':[[['1/3'],0],[[0],0],[['-1/3'],0]]}
    plan = call('sieve',spec)
    try:
        gpu = dispatch(plan)
    except GPUUnavailable as exc:
        pytest.skip(str(exc))
    assert all(row[0] == 0 for row in gpu['rows'])
    assert [row[1] for row in gpu['rows']] == [row[1] for row in plan['results']]
    overflow = {'format':'omega-symbolic-dag-1','variables':1,
                'nodes':[['const',32767,[]],['const',1,[]],['add',0,[0,1]],['sub',0,[2,1]]],'root':3}
    plan = call('sieve',{'programs':[overflow],'observations':[[[0],32767]]})
    assert plan['fits'] == [0]
    result = dispatch(plan)
    assert result['rows'][0][0] == 1


def test_quarantine_has_no_admission_authority():
    good = claim()
    bad = deepcopy(good)
    bad['observations'][0][1] = 100
    result = call('quarantine',{'messages':[good,good,bad]})
    assert len(result['pending_kernel']) == 1
    assert len(result['duplicates']) == len(result['rejected']) == 1
    assert result['admitted'] == result['network_actions'] == 0


def test_peer_signature_replay_expiry_and_content_dedup(tmp_path):
    key = Ed25519PrivateKey.generate()
    store = Store([public_key(key)],database=str(tmp_path/'claims.sqlite'),clock=lambda:1000)
    certificate = certify_claim(claim())
    message = sign(certificate,key,1,now=1000)
    assert store.accept(message)['accepted']
    with pytest.raises(PermissionError,match='replay'):
        store.accept(message)
    assert store.accept(sign(certificate,key,2,now=1000))['duplicate']
    store.close()
    store = Store([public_key(key)],database=str(tmp_path/'claims.sqlite'),clock=lambda:1000)
    with pytest.raises(PermissionError,match='replay'):
        store.accept(message)
    with pytest.raises(PermissionError,match='Expired'):
        store.accept(sign(certificate,key,3,now=1,ttl=1))
    tampered = sign(certificate,key,4,now=1000)
    tampered['body']['sequence'] = 100
    with pytest.raises(Exception):
        store.accept(tampered)
    store.close()


def test_peer_valid_signature_cannot_authorize_a_false_claim():
    key = Ed25519PrivateKey.generate()
    store = Store([public_key(key)],clock=lambda:1000)
    wrong = claim()
    wrong['observations'][0][1] = 99
    with pytest.raises(PermissionError,match='kernel'):
        store.accept(sign(certify_claim(wrong),key,1,now=1000))
    assert store.db.execute('SELECT COUNT(*) FROM claims').fetchone()[0] == 0
    store.close()


def test_peer_quota_is_transactional():
    key = Ed25519PrivateKey.generate()
    store = Store([public_key(key)],max_items=1,clock=lambda:1000)
    store.accept(sign(certify_claim(claim()),key,1,now=1000))
    second = claim()
    second['observations'] = [[[5],6]]
    with pytest.raises(ValueError,match='quota'):
        store.accept(sign(certify_claim(second),key,2,now=1000))
    assert store.db.execute('SELECT COUNT(*) FROM claims').fetchone()[0] == 1
    store.close()


def test_authenticated_peer_rate_quota_is_separate_from_proof_validity():
    key = Ed25519PrivateKey.generate()
    store = Store([public_key(key)],clock=lambda:1000)
    store.rates[public_key(key)] = (1000//60,32)
    with pytest.raises(PermissionError,match='rate limit'):
        store.accept(sign(certify_claim(claim()),key,1,now=1000))
    store.close()


def test_framed_peer_exchange_uses_loopback_only():
    async def exercise():
        key = Ed25519PrivateKey.generate()
        store = Store([public_key(key)],clock=lambda:1000)
        server = await asyncio.start_server(lambda r,w:handle_peer(r,w,store),'127.0.0.1',0)
        async with server:
            port = server.sockets[0].getsockname()[1]
            reader,writer = await asyncio.open_connection('127.0.0.1',port)
            await write_frame(writer,sign(certify_claim(claim()),key,1,now=1000))
            receipt = await read_frame(reader)
            assert receipt['accepted'] and not receipt['stable_code_modified']
            writer.close()
            await writer.wait_closed()
        store.close()
        reader = asyncio.StreamReader()
        reader.feed_data(struct.pack('!I',65537))
        with pytest.raises(ValueError,match='byte limit'):
            await read_frame(reader)
    asyncio.run(exercise())
