from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import pytest
from omega_sovereign.air_fri import prove,verify,statement,P,canonical,lde
from omega_platform.sandbox import trusted
from omega_platform.budget import PROOF_BUDGET
from omega_selfhost.proof import lake_binary


@pytest.mark.parametrize('steps',[8,16,32,128,256])
def test_air_fri_proves_without_trace_reexecution(steps,monkeypatch):
    proof=prove(19,11,steps)
    import omega_sovereign.air_fri as air
    monkeypatch.setattr(air,'lde',lambda *_:pytest.fail('Verifier must not reconstruct trace'))
    assert verify(proof,statement(19,11,steps,proof['statement']['end']))
    assert len(canonical(proof))<2*1024**2


@pytest.mark.parametrize('target',['statement','a_root','q_root','fri_roots','final','a','next','q','folds','path','queries'])
def test_air_fri_rejects_tampering(target):
    original=prove(1,2,16);proof=deepcopy(original)
    if target=='statement':proof['statement']['end']=(proof['statement']['end']+1)%P
    elif target in ('a_root','q_root'):proof[target]='00'*32
    elif target=='fri_roots':proof['fri_roots'][0]='00'*32
    elif target=='final':proof['final'][0]+=1
    elif target in ('a','next','q'):proof['openings'][0][target]['value']+=1
    elif target=='folds':proof['openings'][0]['folds'][0][0]['value']+=1
    elif target=='path':proof['openings'][0]['a']['path'][0]='00'*32
    elif target=='queries':proof['queries']=1
    assert not verify(proof,original['statement'])


def test_air_rejects_invalid_execution_and_budgets():
    with pytest.raises(ValueError):prove(1,1,8,trace=[1]*8)
    with pytest.raises(ValueError):prove(0,1,512)
    with pytest.raises(ValueError):prove(P,1,8)
    assert not verify({'statement':{}},{})


def test_lean_core_compile_and_token_parser():
    root=Path(__file__).resolve().parents[2]
    result=trusted([lake_binary(),'env','lean','../Sovereign.lean'],cwd=root/'formal/tensor',budget=PROOF_BUDGET)
    assert result.ok,result.stdout+result.stderr
    assert 'sorryAx' not in result.stdout and 'depends on axioms' in result.stdout
    assert result.stdout.count('depends on axioms')==4
