"""OM-108: executable checks; source delivery, not a recorded pass."""
from omega_evolution.architecture_search import candidates,compare

def test_architecture_candidates_respect_parameter_budget_and_do_not_promote():
    proposals=candidates([2,100],[1,2],seed=7,count=8,max_parameters=10)
    assert len(proposals)==2 and all(p['parameter_upper_estimate']<=10 for p in proposals)
    observations=compare(proposals,lambda cfg:dict(cfg),lambda model,train,budget,seed:model.update(trained=True),lambda model,held:model['trained'],[],['held'],10)
    assert all(r['heldout'] is True and r['promoted'] is False for r in observations)
