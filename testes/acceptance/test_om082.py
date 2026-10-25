"""OM-082: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_learning.verifier_feedback import reward

def test_reward_is_grounded_in_independent_boolean_verifier():
    feedback=reward({'id':'x'},'wrong',lambda *_:{'valid':False},'kernel',lambda _: 'a'*64)
    assert feedback.reward==0 and feedback.verifier_id=='kernel' and feedback.candidate_hash=='a'*64
    with pytest.raises(ValueError):reward({'id':'x'},'c',lambda *_:{'valid':1},'k',str)
