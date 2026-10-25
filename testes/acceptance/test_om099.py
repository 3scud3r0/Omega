"""OM-099: executable checks; source delivery, not a recorded pass."""
from omega_nextorch.reward_integrity import crosscheck,discrepancy

def test_external_verifier_rejects_development_reward_hacking():
    result=crosscheck({},'exploit',lambda *_:True,lambda *_:False)
    assert result['disagreement'] and not result['accepted']
    assert discrepancy([True,True],[True,False])=={'cases':2,'opportunistic_cases':1,'rate':.5}
