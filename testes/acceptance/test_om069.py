"""OM-069: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_coder.pull_requests import PullRequest,publish

def test_pr_publication_is_denied_before_external_process(signed_authority):
    verifier,mint=signed_authority
    request=PullRequest('owner/repo','candidate','change','Evidence pending')
    with pytest.raises(PermissionError):publish(request,capability=mint(['git.read']),verifier=verifier,principal='agent',approval=None,approval_gate=None)

def test_pr_identity_rejects_command_like_repository():
    with pytest.raises(ValueError):PullRequest('owner/repo;echo','branch','title','body')
