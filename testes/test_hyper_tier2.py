import asyncio,copy,json
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from omega_self_evolve_v2.bridge_lean_filter import LeanBridge,prove_candidate,verify_receipt

SPEC={'variables':{'x':'self>=-2 and self<=2'},'ensures':'result == x+1',
      'examples':[{'inputs':{'x':str(x)},'output':str(x+1)} for x in (-2,0,2)]}


def test_async_elites_need_real_proofs_and_signed_objects(tmp_path):
    key=Ed25519PrivateKey.generate()
    batch={'candidates':[{'ast':['+',['var','x'],['const','1']],'tier1_admissible':False},
                         {'ast':['const','1'],'tier1_admissible':True}]}
    with LeanBridge(signing_key=key,workers=2,queue_capacity=2) as bridge:
        result=asyncio.run(bridge.consume(SPEC,batch,tmp_path/'formal'))
    assert result['accepted']==1 and [r['accepted'] for r in result['results']]==[True,False]
    record=result['results'][0];directory=Path(record['directory'])
    assert (directory/'Candidate.olean').stat().st_size>0
    assert verify_receipt(record['receipt'],directory,public_key=key.public_key(),expected_spec=SPEC)['valid']
    forged=copy.deepcopy(record['receipt']);forged['manifest']['statement']['ast']=['const','0']
    with pytest.raises(PermissionError):verify_receipt(forged,directory,public_key=key.public_key())
    path=directory/'Candidate.olean';path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='artifact'):verify_receipt(record['receipt'],directory,public_key=key.public_key())


def test_specification_binding_and_canonical_variable_order(tmp_path):
    key=Ed25519PrivateKey.generate()
    spec={'variables':{'y':'true','x':'true'},'ensures':'result==x+y',
          'examples':[{'inputs':{'x':'1','y':'2'},'output':'3'}]}
    result=prove_candidate(spec,{'ast':['+',['var','x'],['var','y']]},tmp_path/'proof',signing_key=key)
    encoded=json.loads(json.dumps(result,sort_keys=True))
    assert verify_receipt(encoded,tmp_path/'proof',public_key=key.public_key())['valid']
    with pytest.raises(ValueError,match='another specification'):verify_receipt(encoded,tmp_path/'proof',public_key=key.public_key(),expected_spec=SPEC)
    difference={**spec,'ensures':'result==x-y','examples':[{'inputs':{'x':'1','y':'2'},'output':'-1'}]}
    bounded=prove_candidate(difference,{'ast':['-',['var','x'],['var','y']]},tmp_path/'ordered-boxes',signing_key=key,
                            input_bounds=[[2,3],[0,1]],output_bounds=[-3,-1])
    assert bounded['manifest']['statement']['analysis_bounds']['inputs']==[[0,1],[2,3]]
    assert verify_receipt(bounded,tmp_path/'ordered-boxes',public_key=key.public_key())['valid']


def test_survivor_bit_never_proves_zero_divisor_or_unsatisfiable_post(tmp_path):
    key=Ed25519PrivateKey.generate()
    spec={'variables':{'x':'true'},'ensures':'result*x==1','examples':[{'inputs':{'x':'1'},'output':'1'}]}
    with pytest.raises(ValueError):prove_candidate(spec,{'ast':['/',['const','1'],['var','x']],'tier1_admissible':True},tmp_path/'bad',signing_key=key)
    assert not (tmp_path/'bad/Certificate.olean').exists()


def test_gpu_output_limits_need_their_own_universal_proof(tmp_path):
    key=Ed25519PrivateKey.generate();candidate={'ast':['+',['var','x'],['const','1']],'tier1_admissible':True}
    with pytest.raises(ValueError):prove_candidate(SPEC,candidate,tmp_path/'false-bounds',signing_key=key,input_bounds=[[-2,2]],output_bounds=[0,0])
    receipt=prove_candidate(SPEC,candidate,tmp_path/'bounded',signing_key=key,input_bounds=[[-2,2]],output_bounds=[-1,3])
    assert any(name.startswith('OmegaTierBounds.') for name in receipt['manifest']['admission']['theorems'])
    assert verify_receipt(receipt,tmp_path/'bounded',public_key=key.public_key())['valid']
