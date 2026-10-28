from pathlib import Path
import pytest
from omega_refine_check.contracts import check_program,verify_contract
from omega_refine_check.syntax import lower,parse

PROGRAM='''// Input and result contracts
type Probability = Rational where { self >= 0/1 and self <= 1/1 }
parametro x: Probability = 1/2;
tensor y: Probability = x*(1-x);
mostrar y;
'''


def test_refinement_metadata_and_universal_contract():
    result=check_program(PROGRAM)
    assert result['obligations']==4
    assert result['metadata']==lower(PROGRAM)
    assert '(v0 : ℚ)' in result['source']


@pytest.mark.parametrize('source',[
    'type P = Rational where {self>=0} parametro x:P=-1; mostrar x;',
    'type Empty = Rational where {self>0 and self<0} parametro x:Empty=0; mostrar x;',
    'parametro x=0; tensor y=1/x; mostrar y;',
    'type P = Rational where {self>=0} parametro x:P=1; tensor y:P=x-2; mostrar y;',
])
def test_unproved_refinement_or_division_rejected(source):
    with pytest.raises(ValueError):check_program(source)


def test_nonzero_divisor_requires_explicit_premise():
    result=verify_contract({'x':'self != 0'},'1/x','result*x == 1')
    assert result['obligations']==2
    with pytest.raises(ValueError):verify_contract({'x':'true'},'1/x','result*x == 1')


def test_static_vector_norm_and_denominator():
    result=check_program('type V = Tensor[Rational,3] where {norm(self)<=50} parametro v:V=[3,4,0]; mostrar v;')
    assert result['obligations']==1
    assert verify_contract({'x':'self.denom != 0'},'x','result.denom != 0')['obligations']==1


def test_native_refinement_parser_build_and_tamper(tmp_path):
    from omega_refine_check.compiler import native_metadata,build,audit
    from omega_selfhost.driver import run
    path=tmp_path/'source.omega';path.write_text(PROGRAM)
    assert native_metadata(path)==lower(PROGRAM)
    result=build(path,tmp_path/'model');assert result['refinement_obligations']==4
    assert run(tmp_path/'model')[0]['values']['y']=='1/4'
    assert audit(path,tmp_path/'model')['valid']
    path.write_text(PROGRAM.replace('1/2','1/3'))
    with pytest.raises(ValueError,match='Changed'):audit(path,tmp_path/'model')


def test_no_lean_injection_or_dynamic_refinement_language():
    with pytest.raises(ValueError):parse('by exact False.elim sorry')
    with pytest.raises(ValueError):check_program('type P = Rational where {self>=0} enquanto(1){mostrar x;}')


def test_refined_corpus_case_runs_against_lowered_independent_reference():
    from omega_platform.corpus import load,evaluate
    root=Path(__file__).resolve().parents[1]
    cases=load(root/'testes/corpus.json',root)
    refined=[case for case in cases if case.language=='refined']
    assert refined and all(evaluate(case,root).status=='passed' for case in refined)
