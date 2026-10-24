import pytest
import json
from copy import deepcopy
from omega.generics import Registry,expand,project_ir,project_result
from omega.typesystem import TypeCheckError
from omega.sintaxe import analisar,ErroOmega
from omega.motor_v1 import CompiladorV1,MaquinaV1


def registry(body='x*x',shape=(),returns=()):
    return Registry.from_dict({'format':'omega-generics-1','schema_version':'1.0.0','functions':[
        {'name':'square','parameters':[{'name':'x','shape':list(shape)}],'returns':list(returns),'body':body}]})


def test_scalar_specialization_preserves_values_and_gradients():
    result=expand('parametro x=3;perda l=square(x);gradiente l em x;mostrar l;',registry())
    raw=CompiladorV1().programa(analisar(result.source))
    projected=project_ir(result,raw)
    assert projected['nos']==raw['nos']
    actual=MaquinaV1(projected).executar()
    expected=MaquinaV1(CompiladorV1().programa(analisar('parametro x=3;perda l=x*x;gradiente l em x;mostrar l;'))).executar()
    assert actual.saidas==expected.saidas
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
    ir=project_ir(result,CompiladorV1().programa(analisar(result.source)))
    with pytest.raises(ErroOmega,match='Divisão por zero'):MaquinaV1(ir).executar()


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
    data=project_result(result,data)
    verification=driver.verify_result(data)
    assert verification['valid']
    assert set(data['values'])=={'x','l'}
    assert 'l = 9' in data['outputs']


def test_projection_preserves_complete_reference_log_across_scalar_and_vector_instances():
    for value in range(-4,5):
        source=f'parametro x={value};perda l=square(x);gradiente l em x;mostrar l;'
        program=expand(source,registry())
        actual=MaquinaV1(project_ir(program,CompiladorV1().programa(analisar(program.source)))).executar()
        expected=MaquinaV1(CompiladorV1().programa(analisar(source.replace('square(x)','x*x')))).executar()
        assert actual.saidas==expected.saidas and actual.estado==expected.estado
    for n in range(1,5):
        source='parametro vetor w=['+','.join(str(i) for i in range(n))+'];perda l=square(w);gradientes l;mostrar l;'
        program=expand(source,registry('dot(x,x)',('n',),()))
        actual=MaquinaV1(project_ir(program,CompiladorV1().programa(analisar(program.source)))).executar()
        expected=MaquinaV1(CompiladorV1().programa(analisar(source.replace('square(w)','dot(w,w)')))).executar()
        assert actual.saidas==expected.saidas and actual.estado==expected.estado


def test_cli_generic_build_ir_and_native_verification_with_reproducible_provenance(tmp_path,capsys,monkeypatch):
    from omega.cli import principal
    from omega_selfhost import driver
    from omega.typed_ir import TypedIR
    source=tmp_path/'input.omega';source.write_text('parametro x=3;perda l=square(x);gradiente l em x;mostrar l;')
    templates=tmp_path/'templates.json';templates.write_text(json.dumps(registry().to_dict()))
    binary=tmp_path/'generic';output=tmp_path/'ir.json'
    assert principal(['generic-ir',str(source),'--templates',str(templates),'--saida',str(output)])==0
    assert set(TypedIR.load(output).legacy()['simbolos'])=={'x','l'}
    assert principal(['generic-build',str(source),'--templates',str(templates),'--saida',str(binary)])==0
    capsys.readouterr()
    data,checked=driver.run(binary)
    assert checked['valid'] and set(data['values'])=={'x','l'}
    assert principal(['native-run',str(binary)])==0
    assert 'l = 9' in capsys.readouterr().out
    sidecar=binary.with_suffix('.generics.json');original=sidecar.read_bytes()
    def forbidden(*args,**kwargs):raise AssertionError('Corrupt provenance reached execution')
    monkeypatch.setattr(driver,'isolated_run',forbidden)
    sidecar.write_bytes(original+b' ')
    result=driver.run_checked(binary)
    assert not result.is_ok and not isinstance(result.cause,AssertionError)
    sidecar.unlink()
    result=driver.run_checked(binary)
    assert not result.is_ok and not isinstance(result.cause,AssertionError)


def test_projection_rejects_unrelated_certificate_graph():
    program=expand('parametro x=1;perda l=square(x);',registry())
    ir=CompiladorV1().programa(analisar(program.source))
    result={'ir':ir,'values':{},'certificates':[{'tipo':'gradiente_ir','ir':{}}]}
    with pytest.raises(TypeCheckError,match='before specialization'):project_result(program,result)
