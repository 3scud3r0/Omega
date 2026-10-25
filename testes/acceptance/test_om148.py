"""OM-148: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_platform.quotas import Quota

def test_quota_releases_only_own_reservation_and_revokes_future_work():
    quota=Quota(slots=1,cost=3)
    with quota.reserve(slots=1):
        with pytest.raises(ValueError):
            with quota.reserve(slots=1):pass
        assert quota.used['slots']==1
    assert quota.used['slots']==0
    quota.consume(cost=3)
    with pytest.raises(ValueError):quota.consume(cost=1)
    quota.revoke()
    with pytest.raises(PermissionError):quota.consume(cost=0)
