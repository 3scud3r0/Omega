"""OM-133: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_security.objectives import ObjectiveGuard

def test_objective_cannot_change_without_owner_authorization():
    guard=ObjectiveGuard({'goal':'solve'},'owner',lambda owner,old,new,approval:approval=='explicit')
    assert guard.check({'goal':'solve'})
    with pytest.raises(PermissionError):guard.check({'goal':'publish'})
    with pytest.raises(PermissionError):guard.replace({'goal':'publish'},'invented')
    guard.replace({'goal':'publish'},'explicit');assert guard.check({'goal':'publish'})
