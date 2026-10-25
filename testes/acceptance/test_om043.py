"""OM-043: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_agent.hierarchical_planner import Plan,Task

def test_dependencies_precede_tasks_and_cycle_is_diagnosed():
    plan=Plan([Task('code','code',('spec',)),Task('spec','spec'),Task('review','review',('code',))])
    assert plan.order()==('spec','code','review') and plan.ready(['spec'])==('code',)
    with pytest.raises(ValueError):Plan([Task('a','a',('b',)),Task('b','b',('a',))])
