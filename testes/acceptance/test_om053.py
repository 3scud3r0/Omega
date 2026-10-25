"""OM-053: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_agent.learned_heuristics import LinearHeuristic

def test_learning_improves_synthetic_heldout_error_without_reusing_ids():
    heuristic=LinearHeuristic(1,rate=.1,l2=0)
    baseline=heuristic.evaluate([('held',[1],2)])['mse']
    for i in range(50):heuristic.learn('train'+str(i),[1],2)
    assert heuristic.evaluate([('held',[1],2)])['mse']<baseline
    with pytest.raises(ValueError):heuristic.evaluate([('train0',[1],2)])
