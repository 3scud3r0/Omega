from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal,localcontext
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import subprocess
import pytest
from omega_native.codec import canonical,decode
from omega_native.toolchain import build,result
from omega_native.authority import Authority,create_key,public_hex,GENESIS
from omega_native import api
from omega_platform.sandbox import ExecutionFailure

@pytest.fixture(scope='module')
def authority(tmp_path_factory):
    root=tmp_path_factory.mktemp('native-authority');return Authority(create_key(root/'authority.seed'))

@pytest.mark.parametrize('value',[0,-3,'a\\b\b\f\n"ç',['text',3],{'z':7,'a':[1,'é']},{'é':{'δ':-1}}])
def test_canonical_document_native_matches_host(value):
    assert result('codec',{'value':value})['canonical']==canonical(value)
    assert decode(canonical(value))==value

@pytest.mark.parametrize('value',[0.1,True,None])
def test_document_rejects_inexact_or_unrepresented_values(value):
    with pytest.raises(ValueError):canonical(value)

@pytest.mark.parametrize('op,x',[('sqrt','0'),('sqrt','2'),('sqrt','1/1000000'),('sqrt',str(2**100)),('exp','-32'),('exp','1/3'),('exp','32'),('log','1/4294967296'),('log','3/2'),('log','4294967296')])
def test_analytic_enclosures_against_independent_decimal(op,x):
    pair=list(map(Q,result('math',{'operation':op,'x':x,'bits':32})['interval']))
    with localcontext() as ctx:
        ctx.prec=100;q=Q(x);d=Decimal(q.numerator)/Decimal(q.denominator);actual={'sqrt':Decimal.sqrt,'exp':Decimal.exp,'log':Decimal.ln}[op](d)
        lower=Decimal(pair[0].numerator)/Decimal(pair[0].denominator);upper=Decimal(pair[1].numerator)/Decimal(pair[1].denominator)
        assert lower<=actual<=upper
        if op=='exp':assert pair[1]-pair[0]<=Q(1,2**32)

@pytest.mark.parametrize('x',['-32','-1/3','0','1/3','32'])
def test_trig_enclosures_against_independent_decimal_series(x):
    observed=result('math',{'operation':'trig','x':x,'bits':24})
    with localcontext() as ctx:
        ctx.prec=110;q=Q(x);d=Decimal(q.numerator)/Decimal(q.denominator)
        for op in ('sin','cos'):
            term=d if op=='sin' else Decimal(1);total=term
            for i in range(1,260):
                k=2*i+(1 if op=='sin' else 0);term=-term*d*d/(k*(k-1));total+=term
            lo,hi=map(Q,observed[op]);assert Decimal(lo.numerator)/lo.denominator<=total<=Decimal(hi.numerator)/hi.denominator
            assert hi-lo<Q(1,2**24)

@pytest.mark.parametrize('op,x',[('sqrt','-1'),('log','0'),('exp','33'),('sin','-33')])
def test_analytic_domain_fail_closed(op,x):
    with pytest.raises(ExecutionFailure):result('math',{'operation':op,'x':x,'bits':16})


def test_repl_recovers_without_committing_bad_assignment():
    executed=subprocess.run([build('tools/repl.omega')],input='let a=15/2;\nlet b=8/3;\nmostrar a*b;\nlet a=1/0;\nmostrar a;\nmostrar missing;\n1+;\nsair\n',text=True,capture_output=True,timeout=15)
    assert executed.returncode==0
    assert '20/1 (Inteiro: 20)' in executed.stdout
    assert executed.stdout.count('=> 15/2')==2
    assert 'Divisao por zero' in executed.stdout and 'Variavel desconhecida' in executed.stdout


def test_database_rationals_tampering_and_trusted_anchor(tmp_path,authority):
    data={'v':Q(7,3),'nested':[Q(-9,7),'text']}
    document,permit=authority.database(key='flight',document=data,policy='flight-v1',bounds={'v':['-30','30']},directory=tmp_path/'proof')
    inserted=api.insert(tmp_path,'data.log',GENESIS,'flight',document,authority=authority.public,permit=permit,policy='flight-v1')
    assert api.lookup(tmp_path,'data.log',inserted['head'],'flight')==data
    with pytest.raises(ExecutionFailure):api.audit(tmp_path,'data.log',GENESIS)
    with pytest.raises(ExecutionFailure):api.insert(tmp_path,'data.log',inserted['head'],'flight',document,authority=authority.public,permit=permit,policy='flight-v1')
    path=tmp_path/'data.log';original=path.read_bytes();path.write_bytes(original.replace(b'7/3',b'8/3'))
    with pytest.raises(ExecutionFailure):api.audit(tmp_path,'data.log',inserted['head'])
    path.write_bytes(original[:-1])
    with pytest.raises(ExecutionFailure):api.audit(tmp_path,'data.log',inserted['head'])


def test_database_cas_only_one_concurrent_writer_and_no_symlinks(tmp_path,authority):
    doc,permit=authority.database(key='x',document=1,policy='db-v1',bounds={'':['0','1']},directory=tmp_path/'proof')
    def insert():
        try:return api.insert(tmp_path,'race.log',GENESIS,'x',doc,authority=authority.public,permit=permit,policy='db-v1')
        except ExecutionFailure:return None
    with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(lambda _:insert(),range(2)))
    assert sum(x is not None for x in outcomes)==1
    (tmp_path/'link.log').symlink_to(tmp_path/'race.log')
    with pytest.raises(ExecutionFailure):api.audit(tmp_path,'link.log',next(x for x in outcomes if x)['head'])
    with pytest.raises(ExecutionFailure):api.audit(tmp_path,'../race.log',GENESIS)


def test_failed_bound_never_issues_database_permit(tmp_path,authority):
    with pytest.raises(ValueError):authority.database(key='x',document=Q(31),policy='flight-v1',bounds={'':['-30','30']},directory=tmp_path/'denied')
    assert not (tmp_path/'denied/permit.json').exists()


def test_message_pinned_keys_scope_and_persistent_replay(tmp_path,authority):
    agent=create_key(tmp_path/'pilot.seed')
    message=dict(sender='pilot',recipient='control',channel='flight',nonce='one',payload=canonical({'v':Q(7,3)}))
    permit=authority.message(message,policy='flight-v1',bounds={'v':['-30','30']},directory=tmp_path/'proof')
    packet=api.seal(message,permit,key_path=tmp_path/'pilot.seed')
    options=dict(recipient='control',channel='flight',policy='flight-v1',senders={'pilot':public_hex(agent)},authority=authority.public)
    wrong={**options,'recipient':'other'}
    with pytest.raises(ExecutionFailure):api.receive(tmp_path,'inbox.log',GENESIS,packet,**wrong)
    delivered=api.receive(tmp_path,'inbox.log',GENESIS,packet,**options)
    with pytest.raises(ExecutionFailure):api.receive(tmp_path,'inbox.log',delivered['head'],packet,**options)
    bad=json.loads(json.dumps(packet));bad['signed']['message']['payload']=canonical({'v':Q(99)})
    with pytest.raises(ExecutionFailure):api.receive(tmp_path,'inbox.log',delivered['head'],bad,**options)


def test_native_mcts_hands_candidate_to_lean(tmp_path,authority):
    spec=dict(variables={'x':'true'},ensures='result == x',constants=['0','1'],operators=['+','*'],examples=[dict(inputs={'x':'-1'},output='-1'),dict(inputs={'x':'2'},output='2')])
    output=api.synthesize(spec,tmp_path/'search',signing_key=authority.key,iterations=32,max_nodes=3)
    assert output['formal_admission'] is True
    assert Q(output['loss'])==0 and Path(output['candidate_source']).is_file()
    from omega_self_evolve_v2.bridge_lean_filter import verify_receipt
    assert verify_receipt(output['receipt'],output['proof_directory'],public_key=authority.key.public_key())['valid']


def test_offline_package_dependencies_and_hashes(tmp_path,authority):
    for name in ('base','app'):(tmp_path/name).mkdir();(tmp_path/name/'main.omega').write_text('funcao f(){retornar 1;}')
    checksum=hashlib.sha256((tmp_path/'base/main.omega').read_bytes()).hexdigest()
    lock={'format':'omega-native-lock-1','packages':[{'name':name,'version':'1.0.0','dependencies':deps,'files':[{'path':'main.omega','sha256':checksum}]} for name,deps in [('app',['base']),('base',[])]]}
    permit=authority.packages(lock,policy='packages-v1',directory=tmp_path/'proof')
    request=dict(root=str(tmp_path),lock=lock,authority=authority.public,policy='packages-v1',certificate=permit)
    assert result('package-verify',request,readonly=[tmp_path])['order']==['base','app']
    (tmp_path/'base/main.omega').write_text('corrupted')
    with pytest.raises(ExecutionFailure):result('package-verify',request,readonly=[tmp_path])
    lock['packages'][1]['dependencies']=['app']
    with pytest.raises(ValueError,match='cycle'):authority.packages(lock,policy='packages-v1',directory=tmp_path/'cycle')


def test_automatic_approval_does_not_read_stdin_and_preserves_gates(tmp_path,authority):
    from omega_refine_check.syntax import parse
    actor=create_key(tmp_path/'auto.seed')
    proposal=result('proposal',dict(target='optimizer',base_sha256='1'*64,candidate_sha256='2'*64,proof_sha256='3'*64,old_ns=100,new_ns=70,old_cost=5,new_cost=1))
    permit=authority._issue('incubator.proposal',proposal,'auto-v1',[parse('70 < 100')],tmp_path/'proof')
    request=dict(proposal=proposal,authority=authority.public,certificate=permit,policy='auto-v1',actor='automatic-supervisor',key_root=str(tmp_path),key_path='auto.seed',nonce='one',mode='auto')
    approved=result('approve',request,readonly=[tmp_path]) # sandbox stdin is /dev/null
    assert approved['approved']==1
    actor.public_key().verify(bytes.fromhex(approved['signature']),approved['approval'].encode())
    assert json.loads(approved['approval'])['mode']=='auto'
    request['mode']='manual'
    assert result('approve',request,readonly=[tmp_path])['approved']==0
    request['mode']='auto';request['proposal']['new_ns']=110
    with pytest.raises(ExecutionFailure):result('approve',request,readonly=[tmp_path])


def test_static_arena_without_heap_symbols_under_ubsan(tmp_path):
    from omega_selfhost.driver import ROOT
    obj=tmp_path/'arena.o';binary=tmp_path/'arena'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT),'-c',str(ROOT/'testes/native_static_arena.c'),'-o',str(obj)],check=True,capture_output=True)
    undefined=subprocess.check_output(['nm','-u',str(obj)],text=True)
    assert all(symbol not in undefined for symbol in ('malloc','calloc','realloc','free'))
    subprocess.run(['cc','-std=c11','-fsanitize=undefined','-fno-sanitize-recover=all','-I',str(ROOT),str(ROOT/'testes/native_static_arena.c'),'-o',str(binary)],check=True,capture_output=True)
    subprocess.run([binary],check=True,timeout=10)


def test_hash_full_capacity_tombstone_update_and_reuse():
    request={'operation':'hash','capacity':2,'commands':[['put','a','1/3'],['put','b','2/7'],['get','b'],['remove','a'],['has','a'],['put','c','4/9'],['put','b','5/6'],['get','b'],['get','c']]}
    output=result('collections',request)
    assert output=={'answers':['2/7',1,0,'5/6','4/9'],'size':2}
    with pytest.raises(ExecutionFailure):result('collections',{'operation':'hash','capacity':1,'commands':[['put','a',1],['put','b',2]]})


def test_adjacency_graph_distinguishes_absent_and_zero_weight():
    output=result('collections',{'operation':'graph','vertices':3,'edges':[[0,1,'0'],[1,2,'-1/7']],'queries':[[0,1],[1,0],[1,2]]})
    assert output['edges']==[[1,'0/1'],[0,'0/1'],[1,'-1/7']]
    with pytest.raises(ExecutionFailure):result('collections',{'operation':'graph','vertices':3,'edges':[[3,0,'1']],'queries':[]})


def test_control_simulation_energy_decreases():
    # u=-2*x-2*v, matched by Native.Contracts.pendulum_energy_decreases.
    controller=[[1,-1,-1,0],[1,-1,-1,1],[2,0,1,''],[0,-1,-1,'-2'],[4,2,3,'']]
    rows=result('simulate',{'model':'pendulum','controller':controller,'state':['1/3','1/7'],'steps':12})['trace']
    assert all(Q(row['energy_after'])<Q(row['energy_before']) for row in rows)
    assert all(abs(Q(row['control']))<=30 for row in rows)


def test_native_fitness_hard_barrier_and_multiobjective():
    metrics=dict(scores=['1/2','1'],weights=['1','1'],before=['1'],after=['3/4'],bwt_weight='1',nodes=3,max_nodes=10,previous_energy='2',energy='1',strict_stability=1,latency_ns=100,memory_bytes=192,baseline_ns=200,memory_budget=1000,objectives=['4/5','1/5','0','0'])
    observed=result('fitness',{'metrics':metrics,'benchmark_iterations':1000})
    assert observed['accepted']==1 and Q(observed['score'])>0 and observed['evaluations']==1000
    assert observed['elapsed_ns']>0
    metrics['scores']=['0','1']
    assert Q(result('fitness',metrics)['score'])==0
    metrics['scores']=['1','1'];metrics['energy']='3'
    assert result('fitness',metrics)['accepted']==0


def test_link_manifest_declares_dynamic_scope_and_rejects_changes(tmp_path):
    from omega.modules import link,verify_manifest
    from omega.typesystem import TypeCheckError
    (tmp_path/'entry.omega').write_text('funcao principal(){var x=parsejson("1");print(text(x));retornar 0;}')
    program=link('entry.omega',tmp_path,dynamic=True);manifest=program.manifest()
    assert manifest['inference_mode']=='dynamic' and manifest['types']['format']=='omega-native-dynamic-1'
    verify_manifest(manifest,tmp_path)
    manifest.pop('inference_mode')
    with pytest.raises((TypeCheckError,ValueError)):verify_manifest(manifest,tmp_path)


def test_idle_native_nursery_single_epoch(tmp_path,authority):
    from omega_native.nursery import epoch
    from omega_autotelic.curiosity_engine import CuriosityEngine
    record=epoch(CuriosityEngine(1),tmp_path/'epoch',authority=authority,iterations=32,family='compiler-identity')
    assert record['tier2']['accepted']==1
    assert record['approval_mode']=='auto'
    assert (tmp_path/'epoch/search/candidate.omega').is_file()


def test_gym_live_weight_reload_changes_version_and_resets_search(tmp_path):
    config={'objectives':['4/5','1/5','0','0'],'baseline_ns':100000,'memory_budget':4096}
    path=tmp_path/'weights.json';path.write_text(json.dumps(config))
    request={'root':str(tmp_path),'config':'weights.json','iterations':64,'max_nodes':5,'seed':1,'spec':{'variables':['x'],'constants':['0','1'],'operators':['+','-','*'],'examples':[{'inputs':['-1'],'output':'-1'},{'inputs':['2'],'output':'2'}]}}
    req=tmp_path/'request.json';req.write_text(json.dumps(request));lines=[];updated=False
    process=subprocess.Popen([build(),'gym',req],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        for line in process.stdout:
            lines.append(line)
            if not updated and '[GINASIO]' in line:
                config['objectives']=['1/5','4/5','0','0'];replacement=tmp_path/'weights.tmp';replacement.write_text(json.dumps(config));replacement.replace(path);updated=True
        stdout,stderr=process.communicate(timeout=30)
    finally:
        if process.poll() is None:process.kill();process.wait()
    assert process.returncode==0,stderr
    assert sum('[GINASIO]' in line for line in lines)>=2
    final=json.loads(lines[-1]);assert final['weights_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert final['winner'] and final['expression'] and final['formal_admission']==0


@pytest.fixture(scope='module')
def incubated(tmp_path_factory,authority):
    from omega_native.incubator import prepare
    from omega_self_evolve_v2.bridge_lean_filter import prove_candidate
    root=tmp_path_factory.mktemp('native-incubation');lhs='(((x*10001)-x*10000)*2)-x'
    spec={'variables':{'x':'true'},'ensures':'result == '+lhs,'examples':[{'inputs':{'x':str(x)},'output':str(x)} for x in (-2,0,2)]}
    receipt=prove_candidate(spec,{'ast':['var','x']},root/'proof',signing_key=authority.key)
    prepare(lhs,receipt,root/'proof',root/'incubation',authority=authority,iterations=4096,repeats=5)
    return root/'incubation'


def test_automatic_host_cycle_detects_changed_candidate_before_adoption(incubated,authority):
    from omega_native.incubator import adopt
    path=incubated/'compiler.omega';original=path.read_bytes();path.write_bytes(original+b'\n')
    try:
        with pytest.raises(ValueError,match='artifacts changed'):adopt(incubated,public_key=authority.key.public_key(),approval_mode='auto',install=False)
    finally:path.write_bytes(original)
    assert not (incubated/'.consumed').exists()


def test_automatic_host_cycle_bootstraps_and_consumes_approval(incubated,authority,monkeypatch):
    import builtins
    from omega_native.incubator import adopt
    def forbidden(*args,**kwargs):raise AssertionError('Automatic approval must never prompt')
    monkeypatch.setattr(builtins,'input',forbidden)
    report=adopt(incubated,public_key=authority.key.public_key(),approval_mode='auto',install=False)
    assert report['bootstrapped'] and report['generation']['bootstrap']['fixed_point']
    stages=report['generation']['bootstrap']['stages'];assert stages[2]['binary_sha256']==stages[3]['binary_sha256']
    assert report['adopted'] is False and (incubated/'.consumed').exists()
    with pytest.raises(FileExistsError):adopt(incubated,public_key=authority.key.public_key(),approval_mode='auto',install=False)


@pytest.mark.parametrize('operation,x',[('sqrt','2'),('exp','-2'),('log','1/8'),('log','3/2'),('log','4'),('sin','1/3'),('trig','0')])
@pytest.mark.lean
def test_native_analytic_output_has_checked_lean_object(tmp_path,operation,x):
    from omega_native.analytic import certify
    checked=certify(operation,x,tmp_path/'proof',bits=8)
    assert checked['manifest']['output']==result('math',{'operation':operation,'x':x,'bits':8})
    assert (tmp_path/'proof/Candidate.olean').stat().st_size>0
    assert hashlib.sha256((tmp_path/'proof/Candidate.olean').read_bytes()).hexdigest()==checked['manifest']['olean_sha256']


def test_native_build_preserves_existing_sidecar(tmp_path):
    (tmp_path/'program.c').write_text('preserve')
    with pytest.raises(ValueError,match='existing native build artifact'):build(destination=tmp_path/'program')
    assert (tmp_path/'program.c').read_text()=='preserve'


def test_bootstrap_checks_expected_base_inside_evolution_lock(incubated,authority,tmp_path):
    from omega_self_evolve_v2.cycle import evolve_from_receipt
    record=json.loads((incubated/'proposta_evolucao_001.json').read_text())
    receipt=json.loads((incubated/'tier2-receipt.json').read_text())
    with pytest.raises(ValueError,match='Compiler changed before the locked bootstrap cycle'):
        evolve_from_receipt(record['lhs'],receipt,record['proof_directory'],tmp_path/'not-created',public_key=authority.key.public_key(),expected_source_sha256='0'*64)
    assert not (tmp_path/'not-created').exists()
