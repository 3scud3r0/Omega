"""OM-030: executable checks; source delivery, not a recorded pass."""
import pytest
pytestmark=pytest.mark.lean

from omega.equivalence import differential

def test_case_equivalence_does_not_claim_universal_proof(typed_graph):
    result=differential(typed_graph,typed_graph,[{'x':1},{'x':2}],lambda ir,state:state['x']**2)
    assert result=={'equal_on_cases':True,'checked':2,'universal':False}

def test_disagreement_returns_actual_counterexample(typed_graph):
    calls=[]
    def evaluate(ir,state):calls.append(state);return len(calls)%2
    result=differential(typed_graph,typed_graph,[{'x':9}],evaluate)
    assert result['counterexample']=={'x':9} and result['equal_on_cases'] is False

def test_formal_local_rewrite_contract(lean_case):lean_case(30)
