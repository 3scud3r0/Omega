import json
import os
from pathlib import Path
import struct
import pytest
from hypothesis import given,settings,strategies as st

from omega_zk.execution import Engine,guest,lower,statement,UINT_MAX
from omega_platform.sandbox import ExecutionFailure
from omega_sovereign.models import call
from .reference import execute

ROOT=Path(__file__).resolve().parents[2]

@pytest.fixture(scope='module')
def engine():
    configured=os.environ.get('OMEGA_RISC0_VERIFIER')
    candidates=[Path(configured)] if configured else [ROOT/'build/risc0-verifier/x86_64-unknown-linux-musl/release/omega-risc0',ROOT/'build/risc0-verifier/release/omega-risc0']
    tool=next((p for p in candidates if p.is_file()),None)
    if tool is None:pytest.skip('Optional standalone RISC Zero verifier not built; scripts/setup-zkvm.sh')
    return Engine(tool)


def program(source,result,fuel=1000):
    ir=lower(source);public=statement(source,ir,result,fuel)
    # Emulator only: a digest is not a proof and is not checked by Unicorn.
    from omega_zk.execution import Program
    return Program(guest(ir,public,bytes(32),fuel),public,tuple(ir),fuel)


def test_lowering_reuses_omega_procedural_ast_and_native_target_rejects_private():
    source='funcao principal() { var x=private(7); retornar x+2; }'
    assert lower(source)[0]==['input',0,7]
    with pytest.raises(Exception):call('backend',{'source':source})

@pytest.mark.parametrize('source',[
    'funcao principal() { retornar private(8); }',
    'funcao principal() { retornar private(-1); }',
    'funcao principal() { retornar private(0,1); }',
    'funcao principal() { retornar unknown(0); }',
    'funcao other(x) { retornar x; }',
    'funcao principal() { retornar missing; }',
])
def test_rejects_unsupported_or_ambiguous_inputs(source):
    with pytest.raises(Exception):lower(source)

@given(st.integers(0,10000),st.integers(0,10000))
@settings(max_examples=24,deadline=None,derandomize=True,database=None)
def test_emitted_guest_matches_independent_rv32_cpu(a,b):
    p=program('funcao principal() { var a=private(0); var b=private(1); retornar a*b+a; }',a*b+a)
    code,out,calls=execute(p,[a,b,0,0,0,0,0,0])
    assert code==0 and out==p.journal and calls==[11,12,16]

@pytest.mark.parametrize('operator,a,b,result',[
    ('+',UINT_MAX,1,0),('-',0,1,UINT_MAX),('*',65536,65536,0),('/',3,2,1),('/',3,0,0),('%',3,0,0)
])
def test_overflow_underflow_zero_and_inexact_division_fail_closed(operator,a,b,result):
    p=program(f'funcao principal() {{ retornar private(0){operator}private(1); }}',result)
    code,out,calls=execute(p,[a,b,0,0,0,0,0,0])
    assert code==1 and out==b'' and calls==[11,12]

@pytest.mark.parametrize('operator,a,b,result',[
    ('/',12,3,4),('%',12,5,2),('<',0,1,1),('>=',0,1,0),('>',4,1,1),('<=',4,1,0),
    ('==',5,5,1),('!=',5,5,0),('+',UINT_MAX,0,UINT_MAX),('*',UINT_MAX,1,UINT_MAX)
])
def test_checked_arithmetic_and_comparisons(operator,a,b,result):
    p=program(f'funcao principal() {{ retornar private(0){operator}private(1); }}',result)
    assert execute(p,[a,b,0,0,0,0,0,0])[:2]==(0,p.journal)


def test_control_flow_fuel_and_wrong_private_witness():
    source='funcao principal() { var i=0; var s=0; enquanto(i<private(0)) { i=i+1; s=s+i; } se(s==55) { retornar s; } senao { retornar 0; } }'
    p=program(source,55)
    assert execute(p,[10,0,0,0,0,0,0,0])[:2]==(0,p.journal)
    assert execute(p,[9,0,0,0,0,0,0,0])[:2]==(1,b'')
    p=program(source,55,fuel=4)
    assert execute(p,[10,0,0,0,0,0,0,0])[:2]==(1,b'')
    p=program('funcao principal() { enquanto(1) { var x=0; } retornar 0; }',0,fuel=50)
    assert execute(p,[0]*8)[:2]==(1,b'')


def test_deterministic_binary_and_statement_binding(engine):
    source='funcao principal() { retornar private(0)+private(1); }'
    p=engine.compile(source,10);q=engine.compile(source,10)
    assert p.elf==q.elf and p.journal==q.journal
    assert engine.image_id(p)==engine.image_id(q)
    changed=engine.compile(source,11)
    assert engine.image_id(p)!=engine.image_id(changed)
    # Two witnesses establish the same statement without publishing either.
    assert execute(p,[3,7,0,0,0,0,0,0])[:2]==(0,p.journal)
    assert execute(p,[4,6,0,0,0,0,0,0])[:2]==(0,p.journal)

@pytest.mark.parametrize('bad',[b'',b'junk',bytes(64),b'\xff'*4096])
def test_independent_verifier_rejects_forged_receipts(engine,bad):
    if not bad:
        with pytest.raises(ValueError):engine.verify(bad,'0'*64,b'{}')
    else:
        with pytest.raises(ExecutionFailure):engine.verify(bad,'0'*64,b'{}')


def test_real_succinct_stark_and_tampering(engine,tmp_path):
    configured=os.environ.get('OMEGA_RISC0_PROVER')
    if not configured:pytest.skip('Real prover unavailable; recursion artifact/network prerequisite pending')
    prover=Engine(configured)
    p=prover.compile('funcao principal() { retornar private(0)+private(1); }',10)
    image_id=engine.image_id(p)
    proof,metrics=prover.prove(p,[3,7,0,0,0,0,0,0])
    assert metrics['valid'] and metrics['scheme']=='risc0-succinct-stark-3.0.3'
    assert engine.verify(proof,image_id,p.journal)['valid']
    for damaged,id,public in [(proof[:-1],image_id,p.journal),(proof+b'\0',image_id,p.journal),
        (bytes([proof[0]^128])+proof[1:],image_id,p.journal),(proof,'0'*64,p.journal),(proof,image_id,b'{}')]:
        with pytest.raises(ExecutionFailure):engine.verify(damaged,id,public)
    with pytest.raises(ExecutionFailure):prover.prove(p,[3,8,0,0,0,0,0,0])
    # Exercise the actual cognitive bridge as well as the lower-level SDK.
    # This is an execution certificate, distinct from the Lean theorem and
    # the RV64 specialization verified by test_bicameral.py.
    from omega_cognition.problem import normalize
    from omega_cognition.bridge import seal
    from omega_refine_check.syntax import parse
    problem=normalize(json.loads((ROOT/'omega_cognition/examples/affine.json').read_text()))
    raw,certificate=seal(parse('x+1'),problem,prover=configured,verifier=engine.tool)
    assert raw and certificate['verification']['valid']
    assert 'not a proof of the RV64 binary' in certificate['scope']
