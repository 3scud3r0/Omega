from copy import deepcopy
import itertools
import json
from pathlib import Path

import pytest

from omega.dimensions import DimensionContract,dimension_contract,certify_graph_shapes,verify_graph_shapes
from omega.typesystem import NumericType,TypeCheckError,infer_operation
from omega.motor_v1 import vshape
from omega.sintaxe import ErroOmega

ROOT=Path(__file__).resolve().parents[2]


def test_symbolic_product_requires_all_bindings_and_equal_inner_dimensions():
    contract=dimension_contract('@',(('rows','inner'),('other','cols')))
    assert contract.output==('rows','cols')
    assert contract.specialize({'rows':3,'inner':4,'other':4,'cols':2})==NumericType((3,2))
    for bindings in ({'rows':3,'inner':4,'other':5,'cols':2},{'rows':3},
                     {'rows':True,'inner':4,'other':4,'cols':2},
                     {'rows':2048,'inner':4,'other':4,'cols':2048}):
        with pytest.raises(TypeCheckError):contract.specialize(bindings)


def test_repeated_symbols_propagate_constraints_transitively():
    contract=dimension_contract('+',(('a','b'),('b',3)))
    assert contract.output==(3,3)
    assert contract.specialize({'a':3,'b':3})==NumericType((3,3))
    with pytest.raises(TypeCheckError):contract.specialize({'a':2,'b':3})
    with pytest.raises(TypeCheckError):dimension_contract('+',(('a','a'),(2,3)))


def test_contract_roundtrip_rejects_forged_outputs_and_equations():
    contract=dimension_contract('dot',(('n',),('m',)))
    encoded=json.loads(json.dumps(contract.to_dict()))
    assert DimensionContract.from_dict(encoded)==contract
    for field,value in [('output',[4]),('equalities',[]),('format','omega-dimensions-2'),('extra',0)]:
        changed=deepcopy(encoded);changed[field]=value
        with pytest.raises(TypeCheckError):DimensionContract.from_dict(changed)
    forged=DimensionContract('@',((2,3),(3,4)),(2,5),())
    with pytest.raises(TypeCheckError):forged.specialize({})
    changed=dimension_contract('neg',((1,),)).to_dict();changed['output']=[True]
    with pytest.raises(TypeCheckError):DimensionContract.from_dict(changed)


def test_all_small_concrete_shapes_match_two_existing_independent_type_rules():
    shapes=[(),*(s for rank in (1,2) for s in itertools.product((1,2,3),repeat=rank))]
    comparisons=0
    for operator,arity in [('neg',1),('relu',1),('soma',1),('transposta',1),
                           *[(op,2) for op in ('+','-','*','/','^','@','dot')]]:
        for inputs in itertools.product(shapes,repeat=arity):
            try:expected=vshape(operator,inputs)
            except ErroOmega:
                with pytest.raises(TypeCheckError):dimension_contract(operator,inputs)
                with pytest.raises(TypeCheckError):infer_operation(operator,[NumericType(s) for s in inputs])
            else:
                actual=dimension_contract(operator,inputs).specialize({}).shape
                assert actual==expected==infer_operation(operator,[NumericType(s) for s in inputs]).shape
            comparisons+=1
    assert comparisons==1235


def test_every_corpus_node_checked_and_certificate_bound_to_dimensions():
    from omega_selfhost.driver import compile_ir
    cases=json.loads((ROOT/'testes/corpus.json').read_text())['cases']
    seen=0
    for case in cases:
        if case['language']!='tensor' or case['expected']=='compile_reject':continue
        ir=compile_ir(ROOT/case['path']);cert=certify_graph_shapes(ir)
        assert verify_graph_shapes(ir,cert)
        assert len(cert['nodes'])==len(ir['nos'])
        bad=deepcopy(cert);bad['shape_graph_sha256']='0'*64
        with pytest.raises(TypeCheckError):verify_graph_shapes(ir,bad)
        if cert['nodes']:
            bad=deepcopy(cert);bad['nodes'][0]['shape']=[7]
            with pytest.raises(TypeCheckError):verify_graph_shapes(ir,bad)
        seen+=len(ir['nos'])
    assert seen>100


@pytest.mark.parametrize('mutation',[
    lambda ir:ir['nos'][2].update(forma=[2]),
    lambda ir:ir['nos'][1].update(args=[1]),
    lambda ir:ir['nos'][2].update(op='unchecked'),
    lambda ir:ir['nos'][1].update(forma=[True]),
    lambda ir:ir['parametros'].append({'id':2,'inicial':1}),
])
def test_internal_node_shape_tampering_is_rejected(mutation):
    ir={'nos':[{'op':'num','args':[],'forma':[]},
               {'op':'num','args':[],'forma':[]},
               {'op':'+','args':[0,1],'forma':[]}],'parametros':[]}
    mutation(ir)
    with pytest.raises(TypeCheckError):certify_graph_shapes(ir)


def test_shape_certificate_does_not_accept_boolean_as_integer():
    ir={'nos':[{'op':'zeros','args':[],'forma':[1]}],'parametros':[]}
    cert=certify_graph_shapes(ir);cert['nodes'][0]['shape']=[True]
    with pytest.raises(TypeCheckError):verify_graph_shapes(ir,cert)
