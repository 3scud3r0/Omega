"""OM-104: executable checks; source delivery, not a recorded pass."""
from omega_evolution.synthesis_heuristics import propose,compare

def test_heuristic_mutations_reproduce_and_leave_baseline_unchanged():
    weights={'depth':1.,'cost':2.};candidates=propose(weights,seed=7,count=3)
    assert candidates==propose(weights,seed=7,count=3) and weights=={'depth':1.,'cost':2.}
    report=compare(weights,candidates,[1,2],lambda configuration,cases,budget:sum(configuration.values()),10)
    assert len(report['candidates'])==3 and report['promoted'] is False
