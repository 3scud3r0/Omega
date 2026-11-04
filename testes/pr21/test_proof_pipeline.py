from pathlib import Path
import hashlib
import random
import pytest
from omega_sovereign.native import ROOT,build_crypto
from omega_sovereign.hardware import tool
from omega_sovereign.models import call
from omega_sovereign.air_fri import prove,verify,fft,inv,GENERATOR,P
from omega_platform.sandbox import run,trusted
from omega_platform.budget import COMPILER_BUDGET,PROOF_BUDGET
from omega_selfhost.proof import lake_binary
from omega_sovereign.bft import key,public
from omega_self_evolve_v2.ouroboros import signing


def test_native_fixed_field_x25519_against_independent_implementation(tmp_path):
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey,X25519PublicKey
    binary=tmp_path/'crypto';record=build_crypto(binary,fixed_field=True);rng=random.Random(7748)
    assert record['fixed_control_flow_field'] and not record['production_approved']
    for i in range(8):
        secret=rng.randbytes(32);point=(b'\x09'+bytes(31)) if i==0 else rng.randbytes(32)
        raw=tmp_path/'input';raw.write_bytes(secret+point)
        result=run([tool('qemu-riscv64'),binary,'x25519',raw],readonly=[binary,raw],threads=True,budget=COMPILER_BUDGET)
        reference=X25519PrivateKey.from_private_bytes(secret).exchange(X25519PublicKey.from_public_bytes(point))
        assert result.ok and bytes.fromhex(result.stdout.strip())==reference
    raw.write_bytes(bytes(64))
    assert run([tool('qemu-riscv64'),binary,'x25519',raw],readonly=[binary,raw],threads=True,budget=COMPILER_BUDGET).returncode==6


@pytest.mark.parametrize('steps',[8,16,32,64,128])
def test_omega_fft_and_air_feed_real_fri_verifier(steps):
    native=call('stark',{'start':3,'c':5,'steps':steps})
    assert native['zero_knowledge']==0 and not any(native['residuals'])
    expected=fft(native['trace'],inv(pow(GENERATOR,(P-1)//steps,P)))
    assert native['coefficients']==[(x*inv(steps))%P for x in expected]
    proof=prove(3,5,steps,trace=native['trace'])
    assert verify(proof,proof['statement']) and proof['statement']['end']==native['end']


def test_lean_targets_without_unapproved_axioms():
    result=trusted([lake_binary(),'build','Bisimulation','CompilerCorrectness','ConsensusSafety','CryptoTiming'],cwd=ROOT/'formal/tensor',budget=PROOF_BUDGET)
    assert result.ok,result.stdout+result.stderr
    assert 'sorryAx' not in result.stdout and 'Lean.ofReduceBool' not in result.stdout


def receipt():
    proposer=key(bytes([7])*32);verifier=key(bytes([8])*32)
    evidence={'base_sha256':'1'*64,'candidate_sha256':'2'*64,'proof_sha256':'3'*64,'regression_sha256':'4'*64,
              'cost_before':7,'cost_after':5,'tests_passed':1359,'failures':0,'proof_kind':'lean-universal-rewrite','metric':'generated-probe-ir-nodes'}
    policy={'base_sha256':'1'*64,'proposer_key':public(proposer),'verifier_key':public(verifier),'minimum_tests':1359}
    return proposer,verifier,evidence,policy


def test_independent_ouroboros_receipt_and_tampering_rejection():
    proposer,verifier,evidence,policy=receipt()
    signature=verifier.sign(signing(evidence)).hex()
    assert call('ouroboros',{'policy':policy,'evidence':evidence,'signature':signature})['admitted']==1
    for field,value in [('candidate_sha256','5'*64),('failures',1),('cost_after',7),('tests_passed',1)]:
        damaged={**evidence,field:value}
        with pytest.raises(Exception):call('ouroboros',{'policy':policy,'evidence':damaged,'signature':signature})
    with pytest.raises(Exception):call('ouroboros',{'policy':policy,'evidence':evidence,'signature':proposer.sign(signing(evidence)).hex()})
    with pytest.raises(Exception):call('ouroboros',{'policy':{**policy,'verifier_key':policy['proposer_key']},'evidence':evidence,'signature':signature})
