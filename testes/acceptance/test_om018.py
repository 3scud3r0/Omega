"""OM-018: executable checks; source delivery, not a recorded pass."""
import pytest
import json
from fractions import Fraction
from omega.generics import Registry,ExpansionLimits,expand,project_ir
from omega.typesystem import NumericType,TypeCheckError
from omega.sintaxe import analisar,ErroOmega
from omega.motor_v1 import CompiladorV1,MaquinaV1

def templates():
    return Registry.from_dict({'format':'omega-generics-1','schema_version':'1.0.0','functions':[
        {'name':'norm','parameters':[{'name':'x','shape':['n']}],'returns':[],'body':'dot(x,x)'},
        {'name':'unused','parameters':[{'name':'x','shape':[]}],'returns':[],'body':'0'}]})

def test_specialization_identity_is_deterministic_and_dimensions_are_checked():
    registry=templates()
    a=registry.specialize('norm',(NumericType((3,)),))
    assert a.dimensions==(('n',3),) and a.result==NumericType(())
    assert a.sha256==registry.specialize('norm',(NumericType((3,)),)).sha256
    assert a.sha256!=registry.specialize('norm',(NumericType((2,)),)).sha256
    with pytest.raises(TypeCheckError):registry.specialize('norm',(NumericType(()),))

@pytest.mark.parametrize('n',[1,2,3,5])
def test_expansion_matches_independent_handwritten_program_values_and_gradients(n):
    values=','.join(str(i-2) for i in range(n))
    source=f'parametro vetor w=[{values}];perda l=norm(w);gradientes l;mostrar l;'
    expansion=expand(source,templates())
    actual=MaquinaV1(project_ir(expansion,CompiladorV1().programa(analisar(expansion.source)))).executar()
    expected=MaquinaV1(CompiladorV1().programa(analisar(source.replace('norm(w)','dot(w,w)')))).executar()
    assert actual.saidas==expected.saidas and actual.estado==expected.estado

def test_unused_argument_still_raises_and_limits_are_not_bypassable():
    program=expand('perda l=unused(1/0);mostrar l;',templates())
    with pytest.raises(ErroOmega):MaquinaV1(CompiladorV1().programa(analisar(program.source))).executar()
    with pytest.raises(TypeCheckError):expand('perda l=unused(1);',templates(),limits=ExpansionLimits(steps=1))
    with pytest.raises(TypeCheckError):ExpansionLimits(calls=True)

def test_registry_rejects_recursion_and_duplicate_json(tmp_path):
    path=tmp_path/'templates.json';path.write_text('{"format":"a","format":"b"}')
    with pytest.raises(TypeCheckError):Registry.load(path)
    value=templates().to_dict();value['functions'][0]['body']='norm(x)'
    with pytest.raises(TypeCheckError):Registry.from_dict(value)


def test_registry_collection_and_nested_calls_have_independent_budgets():
    function=next(iter(templates().functions.values()));consumed=[]
    def definitions():
        for i in range(1000):consumed.append(i);yield function
    with pytest.raises(TypeCheckError):Registry(definitions())
    assert len(consumed)==65
    with pytest.raises(TypeCheckError):expand('perda l=unused(unused(1));',templates(),limits=ExpansionLimits(calls=1))


def test_source_limit_counts_utf8_bytes_and_manifest_records_limits():
    source='# é\nperda l=unused(1);'
    with pytest.raises(TypeCheckError):expand(source,templates(),limits=ExpansionLimits(source_bytes=len(source)))
    program=expand(source,templates(),limits=ExpansionLimits(calls=2))
    assert program.manifest()['limits']['calls']==2


def test_cli_rejects_invalid_expansion_budget_before_compiling(tmp_path,capsys):
    from omega.cli import principal
    result=principal(['generic-ir',str(tmp_path/'missing.omega'),'--templates',str(tmp_path/'missing.json'),
                      '--saida',str(tmp_path/'ir.json'),'--max-expansion-steps','0'])
    assert result==1 and not (tmp_path/'ir.json').exists()


def test_driver_uses_captured_template_bytes_before_any_native_build(tmp_path,monkeypatch):
    from omega_selfhost import driver
    source=tmp_path/'source.omega';source.write_text('perda l=unused(1);')
    definition=tmp_path/'templates.json';definition.write_text(json.dumps(templates().to_dict()))
    def forbidden(*args,**kwargs):raise AssertionError('Registry reopened a captured template file')
    monkeypatch.setattr(Registry,'load',forbidden)
    with pytest.raises(TypeCheckError):driver.build_generic(source,definition,tmp_path/'binary',limits=ExpansionLimits(steps=1))
    assert not (tmp_path/'binary').exists()
