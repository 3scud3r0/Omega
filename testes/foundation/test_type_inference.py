import json
from pathlib import Path

import pytest

from omega.typesystem import infer_program,infer_expression,NumericType,RATIONAL,TypeCheckError
from omega.sintaxe import Variavel

ROOT=Path(__file__).resolve().parents[2]


def test_inference_does_not_execute_or_materialize_tensor_values(monkeypatch):
    from omega import motor_v1
    def forbidden(*args,**kwargs):raise AssertionError('Type inference executed a numeric operation')
    monkeypatch.setattr(motor_v1,'mk',forbidden)
    monkeypatch.setattr(motor_v1.MaquinaV1,'executar',forbidden)
    result=infer_program('matriz a=zeros(1000,1000); vetor b=zeros(1000); tensor c=a@b; perda l=soma(c);')
    assert result.symbols['a']==NumericType((1000,1000))
    assert result.symbols['c']==NumericType((1000,))
    assert result.symbols['l']==RATIONAL


@pytest.mark.parametrize('source',[
    'parametro x=[1,2];',
    'vetor x=[[1,2]];',
    'perda l=[1,2];',
    'vetor x=[1,2]+[1];',
    'matriz a=[[1,2]]; vetor b=[1,2,3]; tensor c=a@b;',
    'perda l=missing+1;',
    'perda l=neg(1);',
    'perda l=2^21;',
    'tensor a=zeros(1.5);',
    'perda l=1;gradiente l em missing;',
    'parametro x=1; perda l=x; passo l em x taxa [1];',
    'teorema t=1==[1];',
])
def test_bad_numeric_programs_rejected_before_execution(source):
    with pytest.raises(TypeCheckError):infer_program(source)


def test_proof_variables_and_runtime_value_errors_are_distinct():
    result=infer_program('parametro x=1/0; perda l=x; teorema t=(a+b)^2==a^2+2*a*b+b^2; verificar t;')
    assert result.theorems==frozenset({'t'}) and result.parameters==frozenset({'x'})
    assert result.symbols['x']==RATIONAL
    with pytest.raises(TypeError):result.symbols['x']=NumericType((2,))
    with pytest.raises(TypeCheckError):infer_expression(Variavel('x'),{'x':'unchecked'})


def test_numeric_corpus_types_match_independent_native_frontend():
    from omega_selfhost.driver import compile_ir
    cases=json.loads((ROOT/'testes/corpus.json').read_text())['cases']
    for case in cases:
        if case['language']!='tensor' or case['expected']=='compile_reject':continue
        source=ROOT/case['path']
        types=infer_program(source.read_text())
        ir=compile_ir(source)
        assert {name:list(t.shape) for name,t in types.symbols.items()}=={
            name:ir['nos'][i]['forma'] for name,i in ir['simbolos'].items()},case['path']


def test_inference_depth_is_bounded():
    source='parametro x=1; perda l='+('+'.join(['x']*300))+';'
    with pytest.raises(TypeCheckError,match='budget'):infer_program(source)


def test_large_literals_are_typed_without_disabling_python_integer_limits():
    import sys
    before=sys.get_int_max_str_digits()
    result=infer_program('parametro x='+('9'*6000)+'; vetor a=zeros('+('0'*6000)+'2);')
    assert result.symbols['x']==RATIONAL and result.symbols['a']==NumericType((2,))
    assert sys.get_int_max_str_digits()==before
