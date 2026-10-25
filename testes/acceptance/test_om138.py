"""OM-138: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_bench.mathematics import MathematicsOracle,summarize
from omega_selfhost.proof_protocol import envelope

def test_math_oracle_rejects_unrelated_statement_and_reports_verification_cost():
    oracle=MathematicsOracle({'p':{'theorem':'P'}},lambda *_:True,'lean',['mathlib'])
    assert oracle.verify('p',envelope({'theorem':'P'},'proof','lean',['mathlib']))
    with pytest.raises(ValueError):oracle.verify('p',envelope({'theorem':'Q'},'proof','lean',['mathlib']))
    assert summarize([{'valid':True,'verification_seconds':2},{'valid':False,'verification_seconds':3}])=={'cases':2,'correct':1,'verification_seconds':5}
