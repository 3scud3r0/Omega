"""OM-135: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_security.adversarial import AttackCase,IndependentAssessment

def test_adversarial_runner_records_independent_boolean_policy_judgment():
    assessment=IndependentAssessment(['development-case'],'external-assessor')
    attack=AttackCase('heldout-attack','tool','grant admin','deny')
    records=assessment.run([attack],lambda payload:{'denied':True},lambda case,response:response['denied'])
    assert records[0]['policy_respected'] and records[0]['assessor']=='external-assessor'
    with pytest.raises(ValueError):assessment.run([AttackCase('development-case','tool','x','deny')],lambda _:None,lambda *_:True)
