"""OM-042: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_agent.reasoning_state import Step,ReasoningState

def test_premise_provenance_and_missing_evidence_paths():
    state=ReasoningState(['axiom-P'])
    state.add(Step('s1',('axiom-P',),'Q',('certificate',),1))
    state.add(Step('s2',('s1',),'R',('witness',),.9))
    assert state.provenance('s2')==('axiom-P','s1','s2')
    with pytest.raises(ValueError):state.add(Step('bad',('missing',),'S',(),1))
    assert 'bad' not in state.steps
