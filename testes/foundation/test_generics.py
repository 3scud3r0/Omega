import pytest
from omega.generics import Registry,expand
from omega.typesystem import TypeCheckError
from omega.sintaxe import analisar
from omega.motor_v1 import CompiladorV1,MaquinaV1


def registry(body='x*x',shape=(),returns=()):
    return Registry.from_dict({'format':'omega-generics-1','schema_version':'1.0.0','functions':[
        {'name':'square','parameters':[{'name':'x','shape':list(shape)}],'returns':list(returns),'body':body}]})


def test_scalar_specialization_preserves_values_and_gradients():
    result=expand('parametro x=3;perda l=square(x);gradiente l em x;mostrar l;',registry())
    actual=MaquinaV1(CompiladorV1().programa(analisar(result.source))).executar()
    expected=MaquinaV1(CompiladorV1().programa(analisar('parametro x=3;perda l=x*x;gradiente l em x;mostrar l;'))).executar()
    # Internal declarations remain visible in the legacy interpreter; the
    # specialization API currently preserves requested values and gradients.
    assert actual.saidas[-2:]==expected.saidas[-2:]
    assert actual.estado==expected.estado


def test_symbolic_vector_specialization_and_hygiene():
    r=registry('dot(x,x)',('n',),())
    result=expand('tensor om_generic_0=7;parametro vetor w=[1,2,3];perda l=square(w);gradientes l;',r)
    manifest=result.manifest()
    assert manifest['instances'][0]['dimensions']=={'n':3}
    assert result.source.count('tensor om_generic_0=')==1
    assert 'om_generic_1' in result.source


def test_unused_argument_is_not_erased():
    result=expand('perda l=square(1/0);mostrar l;',registry('0'))
    assert '/' in result.source
    with pytest.raises(Exception):MaquinaV1(CompiladorV1().programa(analisar(result.source))).executar()


def test_incompatible_shapes_and_false_return_contract_rejected():
    with pytest.raises(TypeCheckError):expand('perda l=square([1,2]);',registry())
    with pytest.raises(TypeCheckError):expand('tensor l=square([1,2]);',registry('x',('n',),()))


def test_closed_templates_reject_capture_and_recursion():
    with pytest.raises(TypeCheckError):registry('x+captured')
    with pytest.raises(TypeCheckError):registry('square(x)')


def test_native_specialization_is_verified_by_lean(tmp_path):
    from omega_selfhost import driver
    result=expand('parametro x=3;perda l=square(x);gradiente l em x;mostrar l;',registry())
    source=tmp_path/'expanded.omega';source.write_text(result.source)
    binary=tmp_path/'program';driver.build(source,binary)
    data,verification=driver.run(binary)
    assert verification['valid']
    assert 'l = 9' in data['outputs']
