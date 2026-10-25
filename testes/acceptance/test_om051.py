"""OM-051: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_agent.reasoning_budget import ReasoningBudget

def test_steps_deadline_and_value_per_cost_are_controlled():
    budget=ReasoningBudget(steps=2,seconds=10);budget.spend();budget.spend()
    assert budget.remaining==0
    with pytest.raises(TimeoutError):budget.spend()
    assert budget.allocate({'slow':4,'fast':3},{'slow':4,'fast':1})==('fast','slow')
    with pytest.raises(ValueError):ReasoningBudget(seconds=float('inf'))
