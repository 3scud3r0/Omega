"""OM-125: executable checks; source delivery, not a recorded pass."""
import pytest

def test_approval_is_exact_expiring_independent_and_single_use(approval_authority):
    gate,issue=approval_authority;action={'operation':'publish','target':'branch'}
    approval=issue(action);assert gate.consume(action,approval,'agent')==gate.digest(action)
    with pytest.raises(PermissionError):gate.consume(action,approval,'agent')
    with pytest.raises(PermissionError):gate.consume({'operation':'delete'},issue(action),'agent')
    with pytest.raises(PermissionError):gate.consume(action,issue(action,expires=1),'agent')
    with pytest.raises(PermissionError):gate.consume(action,issue(action),'reviewer')
