"""OM-089: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_nextorch.constrained_generation import ConstrainedDecoder

class Grammar:
    def complete(self,state):return state==2
    def allowed(self,state):return [state]
    def advance(self,state,token):assert state==token;return state+1

def test_masking_respects_grammar_even_when_invalid_token_has_greater_logit():
    tokens,state=ConstrainedDecoder(Grammar(),max_tokens=3).generate(lambda *_:[0,1,100],0,seed=7)
    assert tokens==(0,1) and state==2
    with pytest.raises(TimeoutError):ConstrainedDecoder(Grammar(),max_tokens=1).generate(lambda *_:[0,1,100],0)
