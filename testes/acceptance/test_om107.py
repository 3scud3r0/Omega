"""OM-107: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_evolution.hyperparameters import search

def test_tuning_keeps_total_cost_seed_and_trial_history():
    result=search({'width':[2,4]},lambda configuration,seed,remaining:(configuration['width'],min(2,remaining)),seed=7,trials=10,total_cost=5)
    assert result['spent']==5 and len(result['history'])==3 and [r['seed'] for r in result['history']]==[7,8,9]
    with pytest.raises(ValueError):search({'x':[1]},lambda *_:(1,99),trials=1,total_cost=1)
