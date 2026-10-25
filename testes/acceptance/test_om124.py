"""OM-124: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_tools.simulation import Simulation

def test_simulation_state_actions_reward_and_terminal_contract():
    transitions={'start':{'go':[(1,'done',2)]},'done':{}}
    simulation=Simulation(transitions,'start',terminal=['done'],seed=7)
    assert simulation.actions()==('go',)
    assert simulation.step('go')=={'state':'done','reward':2,'terminal':True,'step':1}
    with pytest.raises(ValueError):simulation.step('go')
    assert simulation.reset()=='start'
