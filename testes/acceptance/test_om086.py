"""OM-086: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_nextorch.model_api import ModelAdapter,ModelRegistry

def test_reasoning_model_can_be_replaced_without_changing_proposal_contract():
    class Model:
        def generate(self,encoded,max_candidates):return iter([encoded+1,encoded+2])
    adapter=ModelAdapter(Model(),lambda p:p['x'],lambda raw:{'candidate':raw})
    registry=ModelRegistry();registry.register('small',adapter)
    assert list(registry.get('small').propose({'x':3},1))==[{'candidate':4}]
    with pytest.raises(ValueError):registry.register('small',adapter)
