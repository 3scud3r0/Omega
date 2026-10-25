"""OM-041: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_agent.problem import Goal,Problem
from omega_agent.integration import boolean_problem

def test_goal_authorization_changes_with_input_or_budget():
    problem=boolean_problem({'id':'p','arity':1,'outputs':[0,1]})
    goal=Goal('p','match table','owner',3)
    original=goal.subject(problem.fingerprint())
    assert original!=Goal('p','match table','owner',4).subject(problem.fingerprint())
    problem.inputs['outputs'][0]=1
    assert original!=goal.subject(problem.fingerprint())

def test_problem_schema_and_snapshot_are_explicit():
    with pytest.raises(ValueError):Problem('p','d',{},(), '')
    problem=Problem('p','d',{'x':1},(),'check')
    assert Problem.from_snapshot(problem.snapshot()).fingerprint()==problem.fingerprint()
