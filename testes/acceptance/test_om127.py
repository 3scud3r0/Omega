"""OM-127: executable checks; source delivery, not a recorded pass."""
from dataclasses import replace
import pytest
from omega_security.encoding import canonical,decode

def test_capability_signature_exact_action_and_absolute_root_are_enforced(signed_authority,tmp_path):
    verifier,mint=signed_authority;token=mint(['code.execute'])
    assert verifier.require(token,'agent','code.execute')['id']=='cap-1'
    with pytest.raises(PermissionError):verifier.require(token,'agent','code')
    claim=decode(token.payload);claim['actions'].append('file.write')
    with pytest.raises(PermissionError):verifier.require(replace(token,payload=canonical(claim)),'agent','file.write')
    claim['actions']='code.execute'
    with pytest.raises(PermissionError):verifier.require(replace(token,payload=canonical(claim)),'agent','code.execute')
    with pytest.raises(PermissionError):verifier.require(token,'agent','code.execute',path=tmp_path.parent)
    with pytest.raises(PermissionError):verifier.require(mint(['code.execute'],expires=1),'agent','code.execute')
