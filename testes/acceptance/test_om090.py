"""OM-090: executable checks; source delivery, not a recorded pass."""
from omega_nextorch.verified_search import search

def test_neural_search_uses_verifier_not_proposal_order():
    class Model:
        def propose(self,problem,limit):return iter(['wrong','correct'])
    result=search({},Model(),lambda x:x,lambda p,c:{'valid':c=='correct','certificate':'checked' if c=='correct' else None})
    assert result['candidate']=='correct' and result['certificate']=='checked'
    assert [row['valid'] for row in result['attempts']]==[False,True]
