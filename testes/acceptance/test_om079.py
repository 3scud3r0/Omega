"""OM-079: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_learning.active_learning import select

def test_active_selection_prefers_uncertainty_per_cost_within_budget():
    result=select([('certain',1,1),('uncertain',.5,1),('expensive',.5,5)],budget=1)
    assert result['ids']==('uncertain',) and result['cost']==1
    with pytest.raises(ValueError):select([('x',.5,0)],budget=1)
