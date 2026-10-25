"""OM-065: executable checks; source delivery, not a recorded pass."""
from omega_coder.program_search import compare,SearchBudget

def test_search_methods_receive_same_candidate_budget_and_seed():
    methods={'enum':lambda rng:iter([0,1,2,3]),'neural':lambda rng:iter([0,1,2,3])}
    result=compare(methods,lambda candidate:candidate==2,SearchBudget(candidates=2,seconds=1,seed=7))
    assert all(r['attempts']==2 and r['solution'] is None and r['seed']==7 for r in result.values())
