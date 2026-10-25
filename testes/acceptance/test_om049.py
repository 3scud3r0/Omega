"""OM-049: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_agent.hypotheses import Hypotheses

def test_posterior_updates_and_impossible_evidence_is_atomic():
    hypotheses=Hypotheses({'a':1,'b':1});hypotheses.update({'a':.9,'b':.1},'observation')
    assert hypotheses.posterior()['a']==pytest.approx(.9)
    before=hypotheses.posterior()
    with pytest.raises(ValueError):hypotheses.update({'a':0,'b':0},'bad')
    assert hypotheses.posterior()==before
