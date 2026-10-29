import asyncio,json
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from omega_autotelic.bank import consolidate,AbstractionBank
from omega_autotelic.curiosity_engine import CuriosityEngine
from omega_autotelic.curiosity_driver import cycle
from omega_self_evolve_v2.bridge_lean_filter import prove_candidate
from omega_self_evolve_v2.cycle import propose_from_profile


def test_native_cse_discovers_then_proves_new_abstraction(tmp_path):
    key=Ed25519PrivateKey.generate();records=[]
    common=['+',['*',['var','x'],['var','x']],['var','x']]
    for i in (1,2):
        ast=['+',common,['const',str(i)]]
        spec={'variables':{'x':'true'},'ensures':f'result == x*x+x+{i}',
              'examples':[{'inputs':{'x':'1'},'output':str(2+i)}]}
        directory=tmp_path/f'accepted-{i}'
        records.append({'directory':str(directory),'receipt':prove_candidate(spec,{'ast':ast},directory,signing_key=key)})
    proposals=consolidate(records,public_key=key.public_key())
    assert proposals and proposals[0]['structural_gain']>0
    bank=AbstractionBank(tmp_path/'bank',public_key=key.public_key())
    entry=bank.promote(proposals[0],signing_key=key)
    assert entry['name'].startswith('abstraction_') and len(bank.entries())==1
    assert (tmp_path/'bank'/entry['id']/'abstraction.omega').is_file()
    from omega.generics import expand
    program=expand('tensor answer='+entry['name']+'(3);mostrar answer;',bank.registry())
    from omega_selfhost.driver import build,run
    source=tmp_path/'macro.omega';source.write_text(program.source);build(source,tmp_path/'macro')
    assert run(tmp_path/'macro')[0]['values']['answer']=='12'
    assert bank.promote(proposals[0],signing_key=key)['id']==entry['id']
    data=json.loads((tmp_path/'bank/bank.json').read_text());data[0]['definition']='funcao evil(){retornar 0;}'
    (tmp_path/'bank/bank.json').write_text(json.dumps(data))
    with pytest.raises(PermissionError):bank.entries()


def test_curiosity_is_seeded_bounded_and_idle_gated(tmp_path):
    a=CuriosityEngine(9);b=CuriosityEngine(9)
    assert [a.task() for _ in range(8)]==[b.task() for _ in range(8)]
    for family in ('affine','polynomial','bounded-control','diophantine-instance','compiler-identity'):
        task=a.task(family);assert task['spec']['examples']
        assert a.observe(task,True)['empirical_uncertainty_bits']>0
    class Busy:
        def idle(self,**kwargs):return False
    key=Ed25519PrivateKey.generate()
    result=asyncio.run(cycle(a,tmp_path/'busy',signing_key=key,backend='host-reference',gate=Busy()))
    assert not result['attempted'] and not (tmp_path/'busy').exists()


def test_explicit_host_reference_idle_epoch_still_requires_tier2(tmp_path):
    key=Ed25519PrivateKey.generate()
    engine=CuriosityEngine(0)
    engine.task=lambda:{'id':'increment','family':'affine','spec':{'variables':{'x':'self>=-1 and self<=1'},
        'ensures':'result==x+1','examples':[{'inputs':{'x':'0'},'output':'1'},{'inputs':{'x':'1'},'output':'2'}]},
        'input_bounds':[[-1,1]],'output_bounds':[0,2]}
    result=asyncio.run(cycle(engine,tmp_path/'epoch',signing_key=key,backend='host-reference',iterations=256))
    assert result['backend']=='host-reference' and result['tier2']['accepted']==1 and not result['optimality_proved']
    proposal=propose_from_profile({'operations':{'*':10,'+':3}})
    assert proposal['lhs']=='(x*2)-x' and not proposal['formal_admission']


def test_supervisor_modules_import_in_a_clean_python_process():
    import subprocess,sys
    result=subprocess.run([sys.executable,'-c','import omega_autotelic.curiosity_driver; import omega_self_evolve_v2.cli'],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
