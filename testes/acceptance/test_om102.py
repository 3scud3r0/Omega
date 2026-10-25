"""OM-102: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_evolution.proposals import Proposal

def test_improvement_hypothesis_binds_baseline_patch_and_cost():
    proposal=Proposal('planner','reduce expansions',.2,5,'a'*64,'author','v1')
    assert proposal.id==Proposal('planner','reduce expansions',.2,5,'a'*64,'author','v1').id
    assert proposal.id!=Proposal('planner','reduce expansions',.2,5,'a'*64,'author','v2').id
    with pytest.raises(ValueError):Proposal('planner','x',.2,0,'a'*64,'author','v1')
