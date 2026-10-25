"""OM-047: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_agent.integration import boolean_problem,boolean_agent
from omega_agent.problem import Goal

class Model:
    def propose(self,problem,limit):return iter([['c',0],['v',0]])

def test_neural_proposals_require_exact_checker_and_authorized_goal(signed_authority,events):
    verifier,mint=signed_authority;problem=boolean_problem({'id':'p','arity':1,'outputs':[0,1]})
    goal=Goal('p','match table','owner',2);subject=goal.subject(problem.fingerprint())
    agent=boolean_agent(Model(),verifier=verifier,principal='agent',audit=events)
    result=agent.solve(problem,goal,mint(['agent.solve'],subject=subject),limit=2)
    assert result['status']=='solved' and result['candidate']==['v',0]
    assert result['attempts'][0]['valid'] is False and result['promoted'] is False
    with pytest.raises(PermissionError):agent.solve(problem,Goal('p','changed','owner',2),mint(['agent.solve'],subject=subject),limit=2)
