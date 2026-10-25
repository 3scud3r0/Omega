"""OM-128: executable checks; source delivery, not a recorded pass."""
from dataclasses import replace
import pytest

def test_dual_role_identity_still_cannot_verify_and_promote_same_proposal(promotion_authority):
    gate,issue,_=promotion_authority;decision=issue()
    gate.roles.assignments['checker']=frozenset(['verifier','promoter'])
    with pytest.raises(PermissionError):gate.authorize(replace(decision,approval=decision.verification),'v1','v0')
