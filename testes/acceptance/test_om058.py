"""OM-058: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_coder.change_plan import Change,plan

def test_multifile_plan_orders_dependencies_and_refuses_cycles():
    changes=[Change('b.py','consumer',('a.py',)),Change('a.py','definition')]
    assert tuple(c.path for c in plan(changes,{})['changes'])==('a.py','b.py')
    with pytest.raises(ValueError):plan([Change('a','a',('b',)),Change('b','b',('a',))],{})
    with pytest.raises(ValueError):Change('../escape','unsafe')
