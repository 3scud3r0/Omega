import pytest
from omega_synth_mcts.search import search
from omega_synth_mcts.pruning import LeanPruner
from omega_synth_mcts.grammar import Grammar,holes,size
from omega_refine_check.syntax import evaluate

SPEC={'variables':{'x':'true'},'ensures':'result == x+1',
      'examples':[{'inputs':{'x':str(x)},'output':str(x+1)} for x in (-2,0,2)]}


def test_mcts_finds_universal_program_and_native_execution(tmp_path):
    from omega_synth_mcts.search import synthesize
    result=synthesize(SPEC,tmp_path/'synthesis',iterations=256,seed=0)
    assert result['verified'] and not result['optimality_proved']
    assert result['expansions']>1 and result['native_admission']
    assert evaluate(result['candidate'],{'x':37})==38


def test_examples_alone_never_certify_a_false_universal_contract():
    spec={'variables':{'x':'true'},'ensures':'result*x == 1',
          'constants':[1],'operators':[],
          'examples':[{'inputs':{'x':'1'},'output':'1'}]}
    result=search(spec,iterations=24,max_nodes=1,max_proof_checks=2)
    assert not result['verified'] and result['rejected']


def test_pruner_needs_a_checked_contradiction():
    pruner=LeanPruner({'x':'true'})
    assert pruner.prune(('/',('hole',),('const','0')))
    assert pruner.certificates[0]['proof']['admission']
    assert not pruner.prune(('/',('hole',),('var','x')))
    assert not pruner.prune(('/',('hole',),('hole',)))


def test_neural_guide_has_no_admission_authority():
    class BadPolicy:
        def priors(self,*args):return [float('nan')]*len(args[1])
    with pytest.raises(ValueError,match='distribution'):search(SPEC,policy=BadPolicy())
    proposal=search(SPEC,iterations=256,verify=False)
    assert proposal['candidate'] and proposal['verified'] is False and proposal['admission'] is None


def test_mcts_budget_and_example_precondition():
    with pytest.raises(ValueError):search(SPEC,iterations=0)
    with pytest.raises(ValueError):search({**SPEC,'variables':{'x':'self>0'}})


def test_isolated_proposal_requires_independent_host_proof():
    from omega_synth_mcts.search import isolated_search
    result=isolated_search(SPEC,iterations=256,seconds=10)
    assert result['sandboxed'] and result['verified'] and result['admission']['admission']['theorems']
