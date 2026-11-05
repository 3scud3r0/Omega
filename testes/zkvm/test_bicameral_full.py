"""Full real-tool CPU command; enabled in CI after Lean/QEMU/prover provisioning."""
import json
import os
from pathlib import Path
import shutil
import pytest

ROOT=Path(__file__).resolve().parents[2]

@pytest.mark.skipif(os.environ.get('OMEGA_BICAMERAL_FULL')!='1',
                    reason='Full Lean/RV64/STARK/BFT command requires the CPU integration runner')
def test_seedless_bicameral_command_and_independent_reverification(tmp_path,capsys):
    from omega.cli import principal
    from omega_cognition.crystallization import verify,digest
    verifier=os.environ['OMEGA_RISC0_VERIFIER'];prover=os.environ['OMEGA_RISC0_PROVER']
    output=Path(os.environ.get('OMEGA_BICAMERAL_EVIDENCE_DIR',str(tmp_path/'discovery')))
    spec=ROOT/'omega_cognition/examples/seedless_affine.json'
    assert 'candidates' not in json.loads(spec.read_text())
    assert principal(['--mode','bicameral','cognition','discover',str(spec),
        '--proposal-source','search','--iterations','512','--proposals','1','--wall-seconds','900',
        '--require-seal','--bft-local','--zk-prover',prover,'--zk-verifier',verifier,'--output',str(output)])==0
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='crystallized' and result['crystallization_complete']
    assert result['configured_stages_complete'] and result['pending_stages']==[]
    row=result['candidates'][0]
    assert row['origin']['sandboxed'] and row['origin']['evaluations']>0
    assert row['empirical']['counts']['iid']==299572
    assert row['empirical']['confidence']['accepted'] and row['formal_admission']
    assert row['native']['observed']=='1/1' and row['zk']['verification']['valid']
    assert row['bft']['converged'] and row['final_bft']['converged']
    assert not result['kernel_activated'] and row['promotion']=='pending_independent_approval'
    final=json.loads((output/'candidate-000/final-ledger-object.json').read_text())
    assert all(ledger[0][1]==digest(final) for ledger in row['final_bft']['honest_ledgers'])
    manifest=output/'candidate-000/crystallization.json'
    assert principal(['cognition','verify',str(manifest),'--expected-problem',str(spec),
                      '--zk-verifier',verifier,'--replay-empirical'])==0
    checked=json.loads(capsys.readouterr().out)
    assert checked['verified'] and checked['empirical_replayed'] and checked['stark']['valid']
    assert not checked['kernel_activated']
    (output/'verification.json').write_text(json.dumps(checked,sort_keys=True,indent=2)+'\n')
    # Rehashing a fabricated proof must still reach and fail the real verifier.
    damaged=tmp_path/'rehashed-proof';shutil.copytree(manifest.parent,damaged)
    proof=damaged/'receipt.stark';proof.write_bytes(b'forged receipt')
    import hashlib
    content=json.loads((damaged/'crystallization.json').read_text())
    content['assets']['receipt.stark']=hashlib.sha256(proof.read_bytes()).hexdigest()
    content['sha256']=digest({k:v for k,v in content.items() if k!='sha256'})
    (damaged/'crystallization.json').write_text(json.dumps(content))
    with pytest.raises(RuntimeError):verify(damaged/'crystallization.json',json.loads(spec.read_text()),verifier=verifier)
    # A constant output must not allow the prover to substitute another input
    # for the experiment's publicly declared sample.
    from omega_cognition.bridge import zk_specialization
    from omega_cognition.problem import normalize
    from omega_refine_check.syntax import parse
    from omega_zk.execution import Engine
    from omega_platform.sandbox import ExecutionFailure
    constant=normalize({'format':'omega-cognitive-problem-1',
        'variables':{'x':{'lower':0,'upper':1,'denominator':1}},'reference':'1',
        'training':[{'inputs':{'x':'0'},'output':'1'}]})
    fixed=zk_specialization(parse('1'),constant,Engine(verifier))
    with pytest.raises(ExecutionFailure):Engine(prover).prove(fixed,[1,0,0,0,0,0,0,0])
