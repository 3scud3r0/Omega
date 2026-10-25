"""OM-098: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_nextorch.routing import Router

def test_router_uses_evidence_cost_and_domain():
    router=Router();router.observe('math','cheap',True,1);router.observe('math','costly',True,10)
    assert router.choose('math',['cheap','costly'])=='cheap'
    with pytest.raises(ValueError):router.choose('unseen',['cheap'])
