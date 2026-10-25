"""OM-066: executable checks; source delivery, not a recorded pass."""
from omega_coder.verified_optimization import optimize

def test_optimization_requires_lean_equivalence_before_comparing_cost(typed_graph):
    result=optimize(typed_graph.legacy(),lambda ir:len(ir['nos'])+1)
    assert result['proof']['valid'] is True and result['baseline_cost']>0
    assert result['candidate_cost']>0 and 'certificate' in result
