"""OM-094: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_nextorch.uncertainty import abstain,selective_risk,entropy

def test_selective_risk_and_abstention_use_observed_coverage():
    assert abstain([.5,.5]) and not abstain([.99,.01])
    result=selective_risk([.9,.6],[True,False],.8)
    assert result=={'coverage':.5,'risk':0.,'accepted':1}
    with pytest.raises(ValueError):entropy([.5,.6])
