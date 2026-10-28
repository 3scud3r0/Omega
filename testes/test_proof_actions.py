import copy
import time
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from omega_agent_sandbox.policy import Policy
from omega_agent_sandbox.actions import prepare
from omega_agent_sandbox.proofs import verify
from omega_agent_sandbox.ledger import Ledger
from omega_agent_sandbox.runtime import Runtime
from omega_agent_sandbox.adapters import Recorder,CallbackAdapter
from omega_security.capabilities import Capability,CapabilityVerifier
from omega_security.revocation import Revocations
from omega_security.encoding import canonical

DATA={'id':'cooling','version':1,'state':{'temperature':'self>=0 and self<=4'},'actions':{
    'cool':{'parameters':{'amount':'self>=0 and self<=1'},'requires':['amount<=temperature'],
            'updates':{'temperature':'temperature-amount'},'effect':'motor'}}}


@pytest.fixture(scope='module')
def action():
    policy=Policy(DATA);key=Ed25519PrivateKey.generate()
    state={'version':0,'values':{'temperature':'3'}}
    proposal={'action':'cool','parameters':{'amount':'1/2'},'nonce':'cool-001','expected_version':0}
    bundle=prepare(policy,state,proposal,signing_key=key)
    return policy,key,state,proposal,bundle


def host(tmp_path,action,adapter=None,subject=None):
    policy,key,state,proposal,bundle=action
    ledger=Ledger(tmp_path/'ledger.sqlite');ledger.initialize('cooling',state['values'])
    authority=Ed25519PrivateKey.generate();revocations=Revocations()
    def signature(issuer,payload,signature):
        if issuer!='host':return False
        try:authority.public_key().verify(signature,payload);return True
        except Exception:return False
    verifier=CapabilityVerifier(signature,revocations)
    claims={'id':'capability-1','principal':'agent','actions':['agent.dispatch.motor'],
            'root':str(tmp_path),'expires':time.time()+300,'subject':subject or bundle['subject']}
    raw=canonical(claims);token=Capability(raw,authority.sign(raw),'host')
    recorder=adapter or Recorder()
    runtime=Runtime(policy,ledger,public_key=key.public_key(),capability_verifier=verifier,principal='agent',adapters={'motor':recorder})
    return runtime,ledger,token,recorder


def test_valid_hoare_action_dispatches_once_and_updates_state(action,tmp_path):
    runtime,ledger,token,adapter=host(tmp_path,action)
    result=runtime.dispatch(action[-1],token)
    assert result['post_state']['values']['temperature']=='5/2'
    assert ledger.snapshot('cooling')['version']==1
    assert len(adapter.receipts)==1
    with pytest.raises(ValueError):runtime.dispatch(action[-1],token)
    assert len(adapter.receipts)==1


@pytest.mark.parametrize('field,value',[('program','tensor x=99;'),('proof','by sorry'),('signature','00'*64),('subject','0'*64)])
def test_tampered_action_never_dispatches(action,tmp_path,field,value):
    runtime,ledger,token,adapter=host(tmp_path,action)
    bundle=copy.deepcopy(action[-1]);bundle[field]=value
    with pytest.raises((ValueError,PermissionError)):runtime.dispatch(bundle,token)
    assert not adapter.receipts and ledger.snapshot('cooling')['version']==0


def test_capability_must_pin_exact_action(action,tmp_path):
    runtime,ledger,token,adapter=host(tmp_path,action,subject='0'*64)
    with pytest.raises(PermissionError):runtime.dispatch(action[-1],token)
    assert not adapter.receipts


def test_uncertain_external_effect_blocks_retries(action,tmp_path):
    calls=[]
    def fail(parameters,**kwargs):calls.append(parameters);raise OSError('Lost acknowledgment')
    runtime,ledger,token,_=host(tmp_path,action,CallbackAdapter(fail))
    with pytest.raises(OSError):runtime.dispatch(action[-1],token)
    assert ledger.operation(action[-1]['subject'])['status']=='uncertain'
    with pytest.raises(RuntimeError):runtime.dispatch(action[-1],token)
    assert len(calls)==1


def test_unsafe_or_stale_action_rejected_before_execution(action):
    policy,key,state,proposal,bundle=action
    with pytest.raises(ValueError):prepare(policy,state,{**proposal,'parameters':{'amount':'5'}},signing_key=key)
    with pytest.raises(ValueError):prepare(policy,state,{**proposal,'expected_version':1},signing_key=key)
