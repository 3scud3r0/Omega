"""Exercise actual containment, native evaluation and Lean admission boundaries."""
import hashlib
import json
import signal
import sys
from pathlib import Path

import pytest
from omega_agent_sandbox.jail import Jail
from omega_cognition.bicameral import Options, run
from omega_cognition.debate import evaluate
from omega_cognition.dream import propose
from omega_cognition.native import call
from omega_cognition.problem import normalize, flat
from omega_cognition.statistics import confidence, required_trials
from omega_refine_check.syntax import parse

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def spec():
    return json.loads((ROOT/'omega_cognition/examples/affine.json').read_text())


def test_statistical_threshold_and_familywise_control():
    assert not confidence(100000, 0)['accepted']
    assert required_trials() == 299572
    assert confidence(299572, 0)['accepted']
    assert not confidence(299571, 0)['accepted']
    assert required_trials(alpha='0.0125') > required_trials()
    assert not confidence(299572, 1)['accepted']
    assert not confidence(0, 0)['accepted']
    result = confidence(100, 0, epsilon='0.1')
    assert result['accepted'] and not result['formal_proof']
    assert result['upper_failure_probability'] != result['bayesian_uniform_prior_upper']


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '0', '1', '-1'])
def test_probability_input_rejection(value):
    with pytest.raises(ValueError): confidence(1, 0, alpha=value)


def python_in_jail(script, jail=None):
    return (jail or Jail()).execute([sys.executable, '-I', '-S', '-c', script], readonly=[Path(sys.base_prefix)/'lib'])


def test_hard_watchdog_crash_and_parent_survival():
    loop = python_in_jail('while True: pass', Jail(wall_seconds=1, cpu_seconds=2))
    assert not loop.ok and loop.timed_out and loop.sandboxed
    crashed = python_in_jail('import os,signal; os.kill(os.getpid(),signal.SIGSEGV)')
    # Bubblewrap transports a child's signal as exit 128+signal.
    assert not crashed.ok and crashed.returncode in (-signal.SIGSEGV, 128+signal.SIGSEGV)
    assert python_in_jail('print(42)').stdout.strip() == '42'


def test_jail_denies_host_writes_network_and_memory_growth(tmp_path):
    outside = tmp_path/'escape'
    assert not python_in_jail(f'open({str(outside)!r},"w").write("bad")').ok
    assert not outside.exists()
    assert not python_in_jail('import socket; socket.socket()').ok
    memory = python_in_jail('x=bytearray(256*1024*1024)', Jail(memory_bytes=64*1024**2))
    assert not memory.ok and memory.sandboxed


def test_native_exact_rationals_and_undefined_candidate(spec):
    names=['x']; request={'width':1, 'oracle':flat(parse('x+1'),names),
        'candidate':flat(parse('x+1'),names),'rows':[['1/3'],['-5/2']]}
    assert call('batch',request)['failures']==0
    request['candidate']=flat(parse('1/x'),names);request['rows']=[['0']]
    result=call('batch',request)
    assert result['failures']==1 and result['oracle_errors']==0
    request['oracle']=request['candidate']
    assert call('batch',request)['oracle_errors']==1


def test_dream_proposals_are_sandboxed_and_never_admitted(spec):
    result=propose(normalize(spec),iterations=64)
    assert result['status']=='proposed' and result['sandboxed']
    assert not result['formal_admission']


def test_optional_neural_proposal_stays_inside_jail(spec):
    pytest.importorskip('torch')
    result=propose(normalize(spec),iterations=8,guide='neural')
    assert result['status']=='proposed' and result['guide']=='neural'
    assert result['sandboxed'] and not result['formal_admission']


def test_creative_extensions_remain_opaque(spec,tmp_path):
    spec['extensions']=['operator exotic(x) { while true {} }']
    result=run(spec,tmp_path/'dream',options=Options(mode='creative',proposals=1,iterations=16))
    assert result['mode']=='dream' and result['status']=='quarantined'
    assert result['extensions'][0]['executed'] is False
    assert not result['kernel_activated']
    assert all(not row['formal_admission'] for row in result['candidates'])


def test_adversarial_counterexample_prevents_all_promotions(spec,tmp_path):
    spec['candidates']=['x-1']
    result=run(spec,tmp_path/'wrong',options=Options(mode='empirical',cases=100,epsilon='0.1',proposals=1))
    row=result['candidates'][0]
    assert row['status']=='falsified' and row['empirical']['counterexample']
    assert row['empirical']['counts']['iid']==0
    assert not row['formal_admission'] and 'bft' not in row and 'native' not in row


def test_real_100000_trials_are_insufficient_for_requested_risk(spec):
    result=evaluate(parse('x+1'),normalize(spec),trials=100000,seed=719,wall_seconds=300)
    assert result['counts']['iid']==100000 and result['counts']['adversarial']>0
    assert result['status']=='insufficient_evidence' and not result['accepted']
    assert result['confidence']['trials']==100000


def test_sampling_grid_success_does_not_imply_universal_rational_proof(tmp_path):
    spec={'format':'omega-cognitive-problem-1','variables':{'x':{'lower':0,'upper':1,'denominator':1}},
          'reference':'0','training':[{'inputs':{'x':'0'},'output':'0'}],'candidates':['x*(x-1)']}
    result=run(spec,tmp_path/'gap',options=Options(mode='bicameral',cases=100,epsilon='0.1',proposals=1,iterations=8,native=False,proposal_source='seeds'))
    row=result['candidates'][0]
    assert row['empirical']['accepted'] and row['status']=='formal_unproved'
    assert not row['formal_admission'] and not result['kernel_activated']


def test_real_bicameral_mutation_lean_and_rv64_chain(spec,tmp_path):
    spec['candidates']=[]
    result=run(spec,tmp_path/'full',options=Options(mode='bicameral',cases=100,epsilon='0.1',proposals=1,iterations=512,proposal_source='search'))
    row=result['candidates'][0]
    assert row['origin']['sandboxed'] and row['origin']['evaluations']>0
    assert not result['crystallization_complete'] and result['configured_stages_complete']
    assert result['pending_stages']==['stark','artifact']
    assert row['status']=='native_emitted' and row['formal_admission']
    assert row['native']['observed']=='1/1'
    assert not row['native']['universal_compiler_equivalence_proved']
    assert row['promotion']=='pending_independent_approval'
    assert not result['zk_verified'] and not result['kernel_activated']
    assert [e['event'] for e in result['events']]==['propose','debate','stable','crystallize','proved','emit']
    previous='0'*64
    for event in result['events']:
        assert event['previous_sha256']==previous
        unsigned={k:v for k,v in event.items() if k!='sha256'}
        previous=hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert previous==event['sha256']
    for name,checksum in result['artifact_sha256'].items():
        assert hashlib.sha256((tmp_path/'full'/name).read_bytes()).hexdigest()==checksum


def test_strict_default_requires_real_lean_not_empirical(spec,tmp_path):
    result=run(spec,tmp_path/'strict',options=Options(native=False,proposals=1))
    assert result['mode']=='strict' and result['iid_trials_executed']==0
    assert result['candidates'][0]['formal_admission']
    assert 'empirical' not in result['candidates'][0]


def test_quota_exhaustion_and_illegal_transitions_fail_closed(spec,tmp_path):
    result=run(spec,tmp_path/'quota',options=Options(mode='empirical',cases=100,max_total_trials=99,proposals=1))
    assert result['stop_reason']=='trial_budget' and not result['candidates'][0]['formal_admission']
    with pytest.raises(RuntimeError):
        call('transition',{'mode':'dream','phase':'dreamed','event':'emit'})
    with pytest.raises(ValueError): Jail(memory_bytes=1)
    with pytest.raises(FileExistsError):run(spec,tmp_path/'quota')


def test_empirical_ledger_binds_evidence_without_formal_promotion(spec,tmp_path):
    result=run(spec,tmp_path/'ledger',options=Options(mode='empirical',cases=100,epsilon='0.1',proposals=1,bft=True))
    row=result['candidates'][0]
    payload=json.loads((tmp_path/'ledger/candidate-000/ledger-object.json').read_text())
    subject=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert row['bft']['converged'] and len(set(row['bft']['processes']))==4
    assert all(ledger[0][1]==subject for ledger in row['bft']['honest_ledgers'])
    assert not row['formal_admission'] and not result['kernel_activated']


def test_failed_experiments_cannot_refund_the_trial_budget(tmp_path):
    spec={'format':'omega-cognitive-problem-1','variables':{'x':{'lower':0,'upper':1,'denominator':1}},
          'reference':'x/x','training':[{'inputs':{'x':'1'},'output':'1'}],'candidates':['1','x/x']}
    result=run(spec,tmp_path/'failed-quota',options=Options(mode='empirical',cases=100,proposals=2,max_total_trials=150))
    assert [row['status'] for row in result['candidates']]==['validation_failed','resource_exhausted']
    assert result['iid_trial_budget_reserved']==100 and not result['iid_accounting_complete']


def test_cli_both_flag_locations_and_legacy_dispatch(spec,tmp_path,capsys):
    from omega.cli import principal
    path=tmp_path/'spec.json';path.write_text(json.dumps(spec))
    for i,args in enumerate((['--mode','empirical','cognition'],['cognition','--mode','empirical'])):
        assert principal([*args,'discover',str(path),'--cases','10','--epsilon','0.5','--proposals','1','--output',str(tmp_path/f'cli{i}')])==0
        result=json.loads(capsys.readouterr().out)
        assert result['mode']=='empirical' and not result['candidates'][0]['formal_admission']
    with pytest.raises(SystemExit): principal(['--mode','dream','native'])
