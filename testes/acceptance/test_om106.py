"""OM-106: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_evolution.planner_tuning import compare

def test_planner_tuning_rejects_training_contamination_and_preserves_budget():
    observed=[]
    def evaluate(configuration,cases,budget):observed.append((cases,budget));return {'expanded':configuration}
    report=compare([1,2],['train'],[{'id':'held'}],evaluate,7)
    assert len(observed)==2 and all(budget==7 for _,budget in observed) and report['promoted'] is False
    with pytest.raises(ValueError):compare([1],['held'],[{'id':'held'}],evaluate,7)
