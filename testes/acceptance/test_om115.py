"""OM-115: executable checks; source delivery, not a recorded pass."""
from omega_evolution.stopping import StopPolicy

def test_evolution_stops_for_stagnation_risk_or_uncertainty():
    policy=StopPolicy(patience=2)
    assert policy.observe((-.1,.1),0,0) is None
    assert policy.observe((-.1,.1),0,0)=='stagnation'
    assert policy.observe((.1,.2),.5,0)=='risk'
    assert policy.observe((.1,.2),0,.9)=='uncertainty'
