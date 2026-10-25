"""OM-123: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_tools.git_ci import inspect,ci_runs

def test_git_and_ci_require_capabilities_before_host_tools(signed_authority,tmp_path):
    verifier,mint=signed_authority
    with pytest.raises(PermissionError):inspect(tmp_path,'status',capability=mint(['other']),verifier=verifier,principal='agent')
    with pytest.raises(PermissionError):ci_runs('owner/repo',capability=mint(['other']),verifier=verifier,principal='agent')
    with pytest.raises(ValueError):ci_runs('owner/repo;echo',capability=mint(['github.ci.read']),verifier=verifier,principal='agent')
