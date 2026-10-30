"""Generated ELF, actual Lean checking, independent contracts and fixed arenas."""
from copy import deepcopy
from fractions import Fraction as Q
from pathlib import Path
import hashlib
import random
import shutil

import pytest
from omega_engines import catalog, run
from omega_engines.execution import arena_native, synthesize
from omega_engines.proof import prove
from omega_platform.budget import BUILD_BUDGET, PROOF_BUDGET
from omega_platform.sandbox import c_tool, trusted, run as isolated_run, instrumented
from omega_science.runtime import ROOT, SOURCE_ROOT, _plain, inspect_lean_transcript
from omega_selfhost.proof import lake_binary
from omega_selfhost.axiom_policy import forbid_admissions
from omega_security.encoding import canonical

ENTRIES={e['id']:e for e in catalog()['engines']}
def request(identifier):return deepcopy(ENTRIES[identifier]['example'])


def test_hypernetwork_candidate_really_compiles_executes_and_has_lean_objects(tmp_path):
    result=synthesize(request(15),tmp_path/'candidate')
    assert result['compiled'] and result['cases_passed']==3 and result['numeric_obligations_verified']
    assert (tmp_path/'candidate/candidate').read_bytes().startswith(b'\x7fELF')
    assert (tmp_path/'candidate/proof/batch-0/Observation.olean').stat().st_size>0
    assert not result['global_program_correctness_proven'] and not result['generalization_proven'] and not result['promoted']
    for name,sha in result['files'].items():assert hashlib.sha256((tmp_path/'candidate'/name).read_bytes()).hexdigest()==sha
    with pytest.raises(FileExistsError):synthesize(request(15),tmp_path/'candidate')


def test_synthesis_false_cases_and_corrupted_source_are_not_accepted(tmp_path,monkeypatch):
    from omega_engines import execution
    wrong={**request(15),'cases':[{'input':[0],'expected':99}]}
    with pytest.raises(ValueError,match='fails'):synthesize(wrong,tmp_path/'wrong')
    assert not (tmp_path/'wrong').exists()
    proposal=run(15,request(15));proposal['source']+='\n# changed\n'
    monkeypatch.setattr(execution,'run',lambda *_:proposal)
    with pytest.raises(ValueError,match='hash'):synthesize(request(15),tmp_path/'corrupt')
    assert not (tmp_path/'corrupt').exists()


def test_independent_case_contract_rejects_a_self_consistently_hashed_bad_program(tmp_path,monkeypatch):
    from omega_engines import execution
    proposal=run(15,request(15))
    proposal['source']='funcao principal(){print(99);print(1);retornar 0;}'
    proposal['source_sha256']=hashlib.sha256(proposal['source'].encode()).hexdigest()
    monkeypatch.setattr(execution,'run',lambda *_:proposal)
    with pytest.raises(ValueError,match='disagrees'):synthesize(request(15),tmp_path/'candidate')
    assert (tmp_path/'candidate/candidate').is_file() and not (tmp_path/'candidate/receipt.json').exists()


@pytest.mark.parametrize('identifier',[3,6,7])
def test_numeric_contracts_are_reconstructed_and_actually_checked_by_lean(identifier,tmp_path):
    result=prove(identifier,request(identifier),tmp_path/'proof')
    assert result['verified'] and result['obligations']>0
    assert not result['scientific_model_accepted'] and not result['compiler_refinement_proven']
    assert list((tmp_path/'proof/proof').rglob('Observation.olean'))
    assert result['global_linear_contract_verified'] == (identifier==3)
    if identifier==3:
        source=(tmp_path/'proof/proof/linear/LinearContract.lean').read_text()
        assert 'engine_lp_global_bound' in source and '(x0 x1 : ℚ)' in source
        assert (tmp_path/'proof/proof/linear/LinearContract.olean').is_file()


def test_a_proposer_cannot_supply_an_incorrect_dual_or_select_a_weaker_contract(tmp_path,monkeypatch):
    from omega_engines import proof
    bad=run(3,request(3));bad['dual']=[Q(0)]*3
    monkeypatch.setattr(proof,'run',lambda *_:bad)
    with pytest.raises(ValueError):prove(3,request(3),tmp_path/'bad')
    with pytest.raises(ValueError,match='No reviewed'):prove(14,request(14),tmp_path/'unsupported')
    assert not (tmp_path/'bad').exists() and not (tmp_path/'unsupported').exists()


def test_proof_receipt_binds_the_checked_input_snapshot(tmp_path,monkeypatch):
    from omega_engines import proof
    data=request(3);snapshot=deepcopy(data);original_run=proof.run
    def mutate_after_execution(identifier,payload):
        result=original_run(identifier,payload);data['c'][0]=999;return result
    monkeypatch.setattr(proof,'run',mutate_after_execution)
    result=prove(3,data,tmp_path/'proof')
    assert data!=snapshot
    assert result['request_sha256']==hashlib.sha256(canonical(_plain(snapshot))).hexdigest()


@pytest.mark.parametrize('data',[dict(A=[[1]],b=[-1],c=[1]),dict(A=[[-1]],b=[-1],c=[1])])
def test_farkas_and_recession_certificates_are_also_kernel_checked(data,tmp_path):
    result=prove(3,data,tmp_path/'proof')
    assert result['verified'] and result['global_linear_contract_verified']
    assert (tmp_path/'proof/proof/linear/LinearContract.olean').is_file()


def test_variational_receipt_cannot_certify_a_different_initial_momentum(tmp_path,monkeypatch):
    from omega_engines import proof
    bad=run(6,request(6));bad['value'][0][1][0]+=1
    monkeypatch.setattr(proof,'run',lambda *_:bad)
    with pytest.raises(ValueError,match='trajectory'):prove(6,request(6),tmp_path/'wrong')
    assert not (tmp_path/'wrong').exists()


def test_discrete_hamilton_principle_is_kernel_checked_without_admissions():
    path=ROOT/'omega_core/formal/HamiltonPrinciple.lean';forbid_admissions(path.read_text())
    trusted([lake_binary(),'build','EngineAxioms'],cwd=ROOT/'formal/tensor',budget=BUILD_BUDGET,check=True)
    result=trusted([lake_binary(),'env','lean',path],cwd=ROOT/'formal/tensor',budget=PROOF_BUDGET,check=True)
    expected={'OmegaEngines.'+name for name in ('action_variation','recurrence_is_stationary','stationary_action_variation',
              'verlet_jacobian_determinant','triangle_exterior_squared_zero','work_energy_balance')}
    assert set(inspect_lean_transcript(result.stdout+result.stderr,expected))==expected


@pytest.mark.parametrize('actors,quantum,mailbox',[(a,q,m) for a in (2,3) for q in (1,2,4) for m in (1,4)])
def test_fixed_c_arenas_reproduce_cooperative_reference_for_different_schedules(tmp_path,actors,quantum,mailbox):
    data={**request(16),'actors':actors,'quantum':quantum,'mailbox_capacity':mailbox,'arena_bytes':4096}
    result=arena_native(data,tmp_path/'native')
    assert result['differential_check_passed'] and result['sandboxed']
    assert result['arena_bytes_allocated']==actors*4096 and result['cell_control_bytes']<4096
    assert not result['process_RSS_measured'] and not result['M_to_N_fibers']


def test_c_microkernel_arithmetic_and_invalid_layout_under_sanitizers(tmp_path):
    rng=random.Random(2026);checks=[]
    for _ in range(100):
        x=Q(rng.randrange(-10**6,10**6),rng.randrange(1,10**6));y=Q(rng.randrange(-10**6,10**6),rng.randrange(1,10**6))
        for op,value in [('ADD',x+y),('MUL',x*y)]:
            checks.append('assert(!omega_micro_arithmetic((OmegaMicroQ){'+str(x.numerator)+','+str(x.denominator)+'},(OmegaMicroQ){'+str(y.numerator)+','+str(y.denominator)+'},OMEGA_MICRO_'+op+',&out));assert(out.n==INT64_C('+str(value.numerator)+')&&out.d==UINT64_C('+str(value.denominator)+'));')
    source=tmp_path/'check.c';header=SOURCE_ROOT/'runtime/cellular_micro_arena.h'
    source.write_text('''#include "cellular_micro_arena.h"
#include <assert.h>
int main(void){
OmegaMicroQ out;
CHECKS
assert(omega_micro_arithmetic((OmegaMicroQ){INT64_MAX,1},(OmegaMicroQ){1,1},OMEGA_MICRO_ADD,&out));
assert(!omega_micro_arithmetic((OmegaMicroQ){INT64_MAX,1},(OmegaMicroQ){-INT64_MAX,1},OMEGA_MICRO_ADD,&out));
assert(out.n==0&&out.d==1);
_Alignas(OmegaMicroCell) unsigned char memory[8192];
OmegaMicroRuntime r;OmegaMicroInstruction code[]={ {OMEGA_MICRO_HALT,0,0,{0,1}} };
assert(!omega_micro_init(&r,memory,sizeof memory,4096,2,2,1,1,code,1));
assert(omega_micro_init(&r,memory,4096,4096,2,2,1,1,code,1));
assert(omega_micro_init(&r,memory+1,8191,4096,1,2,1,1,code,1));
code[0].op=99;assert(omega_micro_init(&r,memory,sizeof memory,4096,2,2,1,1,code,1));
code[0].op=OMEGA_MICRO_SEND;code[0].target=2;
assert(omega_micro_init(&r,memory,sizeof memory,4096,2,2,1,1,code,1));
return 0;}
'''.replace('CHECKS','\n'.join(checks)))
    target=tmp_path/'check';cc=shutil.which('cc');assert cc
    c_tool([cc,'-std=gnu11','-O1','-g','-fno-pie','-no-pie','-fno-omit-frame-pointer','-fsanitize=address,undefined',
            '-I',header.parent,source,'-o',target],inputs=[source,header.parent],output_directory=tmp_path,budget=BUILD_BUDGET,check=True)
    result=instrumented([target],budget=BUILD_BUDGET,check=True)
    assert result.ok and 'Sanitizer' not in result.stderr and 'runtime error:' not in result.stderr


def test_microkernel_header_compiles_as_freestanding_without_os_or_heap_calls(tmp_path):
    source=tmp_path/'freestanding.c';header=SOURCE_ROOT/'runtime/cellular_micro_arena.h'
    source.write_text('#include "cellular_micro_arena.h"\nint step(OmegaMicroRuntime*r){return omega_micro_run(r,10);}\n')
    target=tmp_path/'kernel.o';cc=shutil.which('cc');assert cc
    c_tool([cc,'-std=gnu11','-O2','-ffreestanding','-fno-builtin','-nostdlib','-I',header.parent,'-c',source,'-o',target],
           inputs=[source,header.parent],output_directory=tmp_path,budget=BUILD_BUDGET,check=True)
    output=trusted(['nm','-u',target],budget=BUILD_BUDGET,check=True).stdout
    assert not any(name in output for name in ('malloc','calloc','realloc','free','mmap','printf','pthread'))


def test_public_microkernel_api_rejects_null_uninitialized_and_invalid_actor(tmp_path):
    header=SOURCE_ROOT/'runtime/cellular_micro_arena.h';source=tmp_path/'boundary.c'
    source.write_text('''#include "cellular_micro_arena.h"
#include <assert.h>
int main(void){
 OmegaMicroRuntime r={0};
 assert(omega_micro_cell(0,0)==0);
 assert(omega_micro_quantum(0,0)<0);
 assert(omega_micro_run(0,1)<0);
 assert(omega_micro_run(&r,1)<0);
 _Alignas(OmegaMicroCell) unsigned char memory[4096];
 const OmegaMicroInstruction code[]={{OMEGA_MICRO_HALT,0,0,{0,1}}};
 assert(!omega_micro_init(&r,memory,sizeof memory,4096,1,2,1,1,code,1));
 assert(omega_micro_cell(&r,1)==0);
 assert(omega_micro_quantum(&r,1)<0);
 assert(omega_micro_quantum(&r,UINT32_MAX)<0);
 assert(!omega_micro_run(&r,1));
 assert(r.completed==1);return 0;}
''')
    target=tmp_path/'boundary';cc=shutil.which('cc');assert cc
    c_tool([cc,'-std=gnu11','-O1','-g','-fno-pie','-no-pie','-fno-omit-frame-pointer','-fsanitize=address,undefined',
            '-I',header.parent,source,'-o',target],inputs=[source,header.parent],output_directory=tmp_path,budget=BUILD_BUDGET,check=True)
    assert instrumented([target],budget=BUILD_BUDGET,check=True).ok
