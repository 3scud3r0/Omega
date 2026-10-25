"""OM-111: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_evolution.rollback import Versions
from omega_security.encoding import digest

def test_activation_health_gate_and_persistent_consumed_ticket(tmp_path,promotion_authority,approval_authority):
    gate,issue,_=promotion_authority;approvals,approve=approval_authority
    def authorize(action,authorization):
        return authorization is not None and authorization.action_digest==digest(action) and approvals.authenticate(authorization) is True
    root=tmp_path/'versions'
    versions=Versions(root,promotion_gate=gate,initial_version='v0',initial_artifacts_sha256='b'*64,authorize_rollback=authorize)
    decision=issue();current=versions.activate('v1',decision,lambda version:True)
    assert current['version']=='v1' and current['previous']['version']=='v0'
    next_decision=issue('v2','v1',current['artifacts_sha256'])
    with pytest.raises(ValueError):versions.activate('v2',next_decision,lambda version:False)
    assert versions.current()==current
    action={'format':'omega-rollback-1','current':'v1','target':current['previous'],'authorization_sha256':current['authorization_sha256']}
    assert versions.rollback(approve(action),lambda version:True)['version']=='v0'
    restarted=Versions(root,promotion_gate=gate,initial_version='v0',initial_artifacts_sha256='b'*64)
    with pytest.raises(PermissionError):restarted.activate('v1',decision,lambda version:True)

def test_unconfigured_version_store_cannot_activate_a_forged_flag(tmp_path):
    versions=Versions(tmp_path/'versions')
    with pytest.raises(PermissionError):versions.activate('v1',object(),lambda _:True)
