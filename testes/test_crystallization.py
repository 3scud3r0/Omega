"""Admission failures and hostile artifacts must never produce a complete mind."""
import json
from pathlib import Path

import pytest
from omega_cognition.bicameral import Options, run
from omega_cognition.crystallization import FILES, digest, publish, verify, read

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def spec():
    return json.loads((ROOT/'omega_cognition/examples/affine.json').read_text())


@pytest.mark.parametrize('kwargs',[
    {'mode':'dream'}, {'native':False}, {'zk_prover':'/usr/bin/false'},
    {'mode':'empirical','zk_prover':'/usr/bin/false','zk_verifier':'/usr/bin/false'}])
def test_required_crystallization_rejects_incomplete_configuration(kwargs):
    with pytest.raises(ValueError):Options(require_seal=True,**kwargs)


def test_real_lean_success_does_not_mask_native_failure(tmp_path):
    spec={'format':'omega-cognitive-problem-1','variables':{'x':{'lower':-1,'upper':1,'denominator':1}},
          'reference':'relu(x)','training':[{'inputs':{'x':'-1'},'output':'0'}],'candidates':['relu(x)']}
    result=run(spec,tmp_path/'native-failure',options=Options(mode='strict',proposals=1))
    row=result['candidates'][0]
    assert row['formal_admission'] and row['status']=='native_failed'
    assert not result['configured_stages_complete'] and not result['crystallization_complete']
    assert result['events'][-1]['event']=='fail_emit'
    assert not result['kernel_activated']


def test_negative_rational_cannot_be_labeled_a_u32_crystallization(tmp_path):
    spec={'format':'omega-cognitive-problem-1','variables':{'x':{'lower':0,'upper':1,'denominator':1}},
          'reference':'x-2','training':[{'inputs':{'x':'0'},'output':'-2'}],'candidates':['x-2']}
    result=run(spec,tmp_path/'zk-failure',options=Options(mode='bicameral',proposal_source='seeds',proposals=1,
        cases=100,epsilon='0.1',require_seal=True,zk_prover='/usr/bin/false',zk_verifier='/usr/bin/false'))
    row=result['candidates'][0]
    assert row['formal_admission'] and row['native']['observed']=='-2/1'
    assert row['status']=='zk_failed' and result['events'][-1]['event']=='fail_seal'
    assert not result['crystallization_complete'] and not result['configured_stages_complete']
    assert not (tmp_path/'zk-failure/candidate-000/crystallization.json').exists()


def untrusted_bundle(root,spec):
    root.mkdir()
    for name in FILES:
        path=root/name;path.parent.mkdir(exist_ok=True)
        path.write_bytes(b'untrusted')
    from omega_refine_check.syntax import parse,render
    node=parse('x+1')
    (root/'hypothesis.json').write_text(json.dumps({'format':'omega-cognitive-hypothesis-1','problem':spec,'candidate':render(node),'ast':node}))
    publish(root)
    return root/'crystallization.json'


def test_changed_artifact_rejected_before_proof_execution(spec,tmp_path):
    manifest=untrusted_bundle(tmp_path/'bundle',spec)
    (manifest.parent/'native/candidate.elf').write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash mismatch'):
        verify(manifest,spec,verifier='/usr/bin/false')


def test_rehashed_irrelevant_lean_certificate_is_rejected(spec,tmp_path):
    manifest=untrusted_bundle(tmp_path/'bundle',spec)
    # Hash consistency alone must not convert unrelated Lean into a proof.
    with pytest.raises(ValueError,match='unrelated'):
        verify(manifest,spec,verifier='/usr/bin/false')


def test_operator_expected_statement_cannot_be_replaced(spec,tmp_path):
    manifest=untrusted_bundle(tmp_path/'bundle',spec)
    expected={**spec,'reference':'x+2','training':[{'inputs':{'x':'0'},'output':'2'}]}
    with pytest.raises(ValueError,match='expected problem'):
        verify(manifest,expected,verifier='/usr/bin/false')


def test_scope_cannot_be_escalated_by_rehashing_manifest(spec,tmp_path):
    manifest=untrusted_bundle(tmp_path/'bundle',spec)
    value=json.loads(manifest.read_text());value['scopes']=['whole compiler correctness']
    value['sha256']=digest({k:v for k,v in value.items() if k!='sha256'})
    manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='integrity'):
        verify(manifest,spec,verifier='/usr/bin/false')


def test_artifact_symlinks_and_devices_are_rejected(spec,tmp_path):
    manifest=untrusted_bundle(tmp_path/'bundle',spec)
    file=manifest.parent/'receipt.stark';file.unlink();file.symlink_to('/etc/passwd')
    with pytest.raises(OSError):verify(manifest,spec,verifier='/usr/bin/false')
    with pytest.raises(ValueError):read(manifest.parent,'../escape',100)


def test_cli_required_seal_has_failure_exit_code(spec,tmp_path,capsys):
    from omega_cognition.cli import main
    spec['reference']='x-2';spec['training']=[{'inputs':{'x':'0'},'output':'-2'}];spec['candidates']=['x-2']
    path=tmp_path/'spec.json';path.write_text(json.dumps(spec))
    status=main(['discover',str(path),'--mode','bicameral','--proposal-source','seeds','--proposals','1',
                 '--cases','100','--epsilon','0.1','--require-seal','--zk-prover','/usr/bin/false',
                 '--zk-verifier','/usr/bin/false','--output',str(tmp_path/'cli')])
    assert status==1 and not json.loads(capsys.readouterr().out)['crystallization_complete']


def test_variable_order_does_not_change_generated_theorem():
    from omega_cognition.problem import normalize
    from omega_cognition.bridge import hypothesis_to_lemma
    from omega_refine_check.syntax import parse
    domain={'lower':0,'upper':2,'denominator':1}
    a={'format':'omega-cognitive-problem-1','variables':{'y':domain,'x':domain},'reference':'x+y',
       'training':[{'inputs':{'x':'0','y':'1'},'output':'1'}]}
    b={**a,'variables':{'x':domain,'y':domain}}
    assert hypothesis_to_lemma(parse('y+x'),normalize(a))==hypothesis_to_lemma(parse('y+x'),normalize(b))


@pytest.mark.parametrize('literal',['-1','-1/3','0','1/3'])
def test_ast_roundtrip_preserves_formal_obligations(literal):
    from omega_cognition.bridge import hypothesis_to_lemma
    from omega_cognition.problem import normalize
    from omega_cognition.crystallization import decode
    from omega_refine_check.syntax import tree
    node=('const',literal)
    spec={'format':'omega-cognitive-problem-1','variables':{'x':{'lower':0,'upper':1,'denominator':1}},
          'reference':literal,'training':[{'inputs':{'x':'0'},'output':literal}]}
    restored=tree(decode(json.dumps({'ast':node}).encode())['ast'])
    assert hypothesis_to_lemma(node,normalize(spec))==hypothesis_to_lemma(restored,normalize(spec))
