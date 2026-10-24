from copy import deepcopy
import json
from pathlib import Path
import random
import sys

import pytest

from omega.typed_ir import TypedIR,validate_legacy,MAX_BYTES
from omega.typesystem import TypeCheckError
from omega.motor_v1 import CompiladorV1
from omega.sintaxe import analisar

ROOT=Path(__file__).resolve().parents[2]


def graph():
    return CompiladorV1().programa(analisar('parametro x=2; perda l=(x-1)^2; gradiente l em x; passo_livre l em x taxa 1/8; mostrar l;'))


def encoded(document):return json.dumps(document,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()


def test_canonical_bytes_independent_of_object_insertion_order_and_immutable():
    def reverse(value):
        if type(value) is dict:return {k:reverse(v) for k,v in reversed(list(value.items()))}
        if type(value) is list:return [reverse(v) for v in value]
        return value
    original=graph();ir=TypedIR.from_legacy(original)
    assert ir.to_bytes()==TypedIR.from_legacy(reverse(original)).to_bytes()
    assert ir.sha256==TypedIR(ir.to_bytes()).sha256
    original['nos'][0]['v']='99'
    copy=ir.to_dict();copy['graph']['nos'][0]['v']='98'
    assert ir.legacy()['nos'][0]['v']=='2'


@pytest.mark.parametrize('mutation',[
    lambda d:d.update(schema_version='2.0.0'),
    lambda d:d.update(format='omega-typed-ir-2'),
    lambda d:d.update(dialect='python'),
    lambda d:d.update(unknown=0),
    lambda d:d['types'][0].update(element='float'),
    lambda d:d['graph'].update(versao='9.0.0'),
    lambda d:d['graph']['nos'][0].update(extra='hidden'),
    lambda d:d['graph']['nos'][0].update(v='2/2'),
    lambda d:d['graph']['nos'][0].update(v='-0'),
    lambda d:d['graph']['nos'][0].update(v='1/0'),
    lambda d:d['graph']['nos'][0].update(v='1e9'),
    lambda d:d['graph']['simbolos'].update(x=0),
    lambda d:d['graph']['parametros'][0].update(nome='other'),
    lambda d:d['graph']['parametros'].clear(),
    lambda d:d['graph']['perdas'].update(l=1),
    lambda d:d['graph']['comandos'][0].update(nome='missing'),
    lambda d:d['graph']['comandos'][2].update(parametro='missing'),
    lambda d:d['graph']['comandos'][3].update(taxa=9999),
    lambda d:d['graph']['comandos'][3].update(semente=True),
])
def test_tampered_schema_values_types_tables_and_commands_rejected(mutation):
    document=TypedIR.from_legacy(graph()).to_dict();mutation(document)
    with pytest.raises(TypeCheckError):TypedIR(encoded(document))


@pytest.mark.parametrize('raw',[
    b'{"format":"omega-typed-ir-1","format":"other"}',
    b'{"number":NaN}',b'{"number":Infinity}',b'{"number":true}',
    b'{"number":1.5}',b'\xff',b'{"value":"\\ud800"}',
    b'['*1000+b']'*1000,
])
def test_malformed_and_ambiguous_json_fails_closed(raw):
    with pytest.raises(TypeCheckError):TypedIR(raw)


def test_noncanonical_whitespace_and_oversize_file_rejected(tmp_path):
    ir=TypedIR.from_legacy(graph())
    with pytest.raises(TypeCheckError,match='canonical'):TypedIR(ir.to_bytes()+b'\n')
    path=tmp_path/'huge.json';path.write_bytes(b' '*(MAX_BYTES+1))
    with pytest.raises(TypeCheckError,match='budget'):TypedIR.load(path)


def test_large_canonical_rational_does_not_change_python_global_limits():
    original=graph();original['nos'][0]['v']='9'*6000
    before=sys.get_int_max_str_digits()
    assert TypedIR.from_legacy(original).legacy()['nos'][0]['v']=='9'*6000
    assert sys.get_int_max_str_digits()==before


def test_false_identity_is_structurally_valid_but_never_admitted_by_ir_reader():
    ir={'formato':'omega-ir-2','versao':'1.0.0','nos':[],'simbolos':{},'parametros':[],'perdas':{},
        'comandos':[{'tipo':'provar','nome':'','left':['n','1'],'right':['n','2']}]}
    assert TypedIR.from_legacy(ir).legacy()==ir
    # The validator is data/type checking, not a theorem oracle.
    for ast in (['call','read',[['n','1']]],['bin','^',['v','x'],['v','n']],
                ['bin','+',['list',[['n','1']]],['n','1']],['un','evil',['n','1']]):
        bad=deepcopy(ir);bad['comandos'][0]['left']=ast
        with pytest.raises(TypeCheckError):TypedIR.from_legacy(bad)


def test_bounded_json_mutations_never_escape_as_untyped_exceptions():
    rng=random.Random(14);document=TypedIR.from_legacy(graph()).to_dict()
    accepted=0
    for _ in range(300):
        bad=deepcopy(document);containers=[bad]
        for _ in range(rng.randrange(1,6)):
            current=containers[-1]
            children=[x for x in (current.values() if type(current) is dict else current) if type(x) in (dict,list)]
            if not children:break
            containers.append(rng.choice(children))
        current=containers[-1]
        if not current:continue
        key=rng.choice(list(current) if type(current) is dict else list(range(len(current))))
        if rng.randrange(2):current[key]=rng.choice([None,True,False,-1,2**40,'unknown',[],{}])
        elif type(current) is dict:del current[key]
        else:current.pop(key)
        try:TypedIR(encoded(bad));accepted+=1
        except TypeCheckError:pass
    assert accepted<10


def test_corpus_original_and_optimized_graphs_roundtrip_without_semantic_rewriting():
    from omega_selfhost.driver import compile_ir
    cases=json.loads((ROOT/'testes/corpus.json').read_text())['cases']
    count=0
    for case in cases:
        if case['language']!='tensor' or case['expected']=='compile_reject':continue
        for optimize in (False,True):
            legacy=compile_ir(ROOT/case['path'],optimize)
            ir=TypedIR.from_legacy(legacy)
            assert TypedIR(ir.to_bytes()).legacy()==legacy
            count+=1
    assert count>=40


def test_cli_exports_validates_and_refuses_overwriting_existing_ir(tmp_path,capsys):
    from omega.cli import principal
    path=tmp_path/'typed.json'
    source=ROOT/'exemplos/rede_profunda.omega'
    assert principal(['native-ir',str(source),'--saida',str(path)])==0
    first=json.loads(capsys.readouterr().out)
    assert first['sha256']==TypedIR.load(path).sha256
    original=path.read_bytes()
    assert principal(['validate-ir',str(path)])==0
    assert json.loads(capsys.readouterr().out)['sha256']==first['sha256']
    assert principal(['native-ir',str(source),'--saida',str(path)])==1
    assert 'ERRO' in capsys.readouterr().err and path.read_bytes()==original
