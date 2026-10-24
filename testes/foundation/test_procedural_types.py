import pytest

from omega.procedural_types import infer_procedural
from omega.typesystem import TypeCheckError


@pytest.mark.parametrize('source',[
    'funcao principal(){retornar 0;}',
    'funcao principal(){retornar principal();}',
    'funcao f(n){se(n==0){retornar 0;}retornar f(n-1);}funcao principal(){retornar f(5);}',
    'funcao f(x){retornar x+x;}funcao principal(){print(f("ok"));print(f(2));retornar 0;}',
    'funcao principal(){var a=[];var i=0;enquanto(i<4){push(a,i);i=i+1;}print(json(a));retornar 0;}',
    'funcao inc(s){put(s,"n",s["n"]+1);retornar s["n"];}funcao principal(){var s=obj();put(s,"n",0);print(inc(s));retornar 0;}',
    'funcao principal(){var a=[1,"x"];print(a[0]+1);print(a[1]+"y");retornar 0;}',
    'funcao principal(){var a=parsejson(read("data.json"));se(isnum(a)){print(a+1);}retornar 0;}',
    'funcao principal(){var a=obj();put(a,"n",1);var b=parsejson(json(a));print(b["n"]+1);retornar 0;}',
    'funcao principal(){var a=[];var i=0;enquanto(i<3){var o=obj();put(o,"n",i);push(a,o);i=i+1;}print(a[0]["n"]+1);retornar 0;}',
])
def test_closed_world_procedural_inference(source):
    result=infer_procedural(source)
    assert 'principal' in result.checked_functions


@pytest.mark.parametrize('body',[
    'print("bad"-1);retornar 0;',
    'var a=[1];print(a+1);retornar 0;',
    'var s=obj();put(s,"x","bad");print(s["x"]+1);retornar 0;',
    'var s=obj();put(s,"x",1);put(s,"x","bad");retornar 0;',
    'var a=[1,"x"];a=["x",1];print(a[0]+1);retornar 0;',
    'var a=obj();put(a,"x",1);var b=obj();a=b;put(b,"x","s");print(a["x"]+1);retornar 0;',
    'var a=[];push(a,a);retornar 0;',
    'var a=[1];var i=0;enquanto(i<3){print(a[i]+1);push(a,"bad");i=i+1;}retornar 0;',
    'var a=parsejson(read("data.json"));print(a+1);retornar 0;',
    'var s=json(1);s=json(obj());print(parsejson(s)+1);retornar 0;',
    'var a=obj();var b=obj();var l=[a,b];var i=1;var x=l[i];put(x,"n",1);put(b,"n","s");print(x["n"]+1);retornar 0;',
    'write(3,"data");retornar 0;',
    'retornar "string";',
    'print(missing);retornar 0;',
    'retornar unknown(1);',
    'print(1,2);retornar 0;',
    'parar;retornar 0;',
])
def test_invalid_procedural_programs_rejected(body):
    with pytest.raises(TypeCheckError):infer_procedural('funcao principal(){'+body+'}')


def test_type_inference_does_not_read_files(monkeypatch):
    import builtins
    def forbidden(*args,**kwargs):raise AssertionError('type checker performed I/O')
    monkeypatch.setattr(builtins,'open',forbidden)
    assert infer_procedural('funcao principal(){print(read("missing"));retornar 0;}')


def test_unused_function_definitions_are_checked_too():
    with pytest.raises(TypeCheckError):
        infer_procedural('funcao bad(){retornar "x"-1;}funcao principal(){retornar 0;}')
    result=infer_procedural('funcao id(x){retornar x;}funcao principal(){retornar 0;}')
    assert set(result.checked_functions)=={'principal','id'}


def test_postcondition_of_failing_guard_and_lexical_shadowing():
    source='''funcao text_only(x){se(!isstr(x)){fail("string required");}retornar x+"!";}
funcao principal(){var x=1;se(isnum(x)){var x="inner";print(x);}print(text_only(parsejson("1")));retornar 0;}'''
    assert infer_procedural(source)
    with pytest.raises(TypeCheckError):
        infer_procedural('funcao principal(){var x=1;se(!isnum(x)){fail("number required");}var x=2;retornar 0;}')


def test_recursive_mutation_does_not_reuse_unchecked_heap_facts():
    source='''funcao f(n,o){
se(n<=0){put(o,"x","s");retornar 0;}
var p=obj();f(n-1,p);print(p["x"]+1);retornar 0;
}
funcao principal(){var o=obj();retornar f(1,o);}'''
    with pytest.raises(TypeCheckError):infer_procedural(source)


def test_typed_values_escaping_into_opaque_json_lose_mutable_field_assumptions():
    source='''funcao principal(){
var child=obj();put(child,"n",1);var o=parsejson("{}");
se(!isnum(o)&&!isstr(o)&&!islist(o)){
put(o,"child",child);var alias=o["child"];
se(!isnum(alias)&&!isstr(alias)&&!islist(alias)){put(alias,"n","bad");}
print(child["n"]+1);
}retornar 0;}'''
    with pytest.raises(TypeCheckError):infer_procedural(source)


def test_operator_type_matrix_against_real_c_runtime(tmp_path):
    from pathlib import Path
    from itertools import product
    from omega_selfhost.driver import cc
    from omega_platform.sandbox import run
    binary=tmp_path/'operators'
    cc(Path(__file__).with_name('type_ops_harness.c'),binary)
    values=[('1','1'),('"s"','"s"'),('[1]','[1]'),('obj()','{}')]
    accepted=rejected=0
    for operator,(left,left_json),(right,right_json) in product(
            ['+','-','*','/','%','<','<=','>','>=','==','!=','&&','||'],values,values):
        source=f'funcao principal(){{print(json({left}{operator}{right}));retornar 0;}}'
        try:infer_procedural(source);typed=True
        except TypeCheckError:typed=False
        outcome=run([binary,operator,left_json,right_json])
        assert outcome.returncode in (0,1),outcome.stderr
        assert typed==outcome.ok,(operator,left,right,outcome.stderr)
        accepted+=typed;rejected+=not typed
    assert accepted+rejected==208 and accepted and rejected


def test_native_build_rejects_bad_types_before_invoking_c_compiler(tmp_path,monkeypatch):
    from omega_selfhost import driver
    compiler=driver.compiler()
    monkeypatch.setattr(driver,'compiler',lambda:compiler)
    def forbidden(*args,**kwargs):raise AssertionError('C compiler ran for an ill-typed program')
    monkeypatch.setattr(driver,'cc',forbidden)
    source=tmp_path/'bad.omega';source.write_text('funcao principal(){print("bad"-1);retornar 0;}')
    target=tmp_path/'bad'
    with pytest.raises(TypeCheckError):driver.build(source,target)
    assert not target.exists() and not target.with_suffix('.c').exists()
