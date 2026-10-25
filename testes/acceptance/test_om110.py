"""OM-110: executable checks; source delivery, not a recorded pass."""
import json
from dataclasses import replace
import pytest
from omega_security.encoding import canonical

def test_promotion_requires_signed_exact_payload_and_rechecks_artifacts(promotion_authority):
    gate,issue,file=promotion_authority;decision=issue()
    assert gate.authorize(decision,'v1','v0',baseline_artifacts_sha256='b'*64)['promoter']=='publisher'
    modified=json.loads(decision.payload);modified['version']='forged'
    with pytest.raises(PermissionError):gate.authorize(replace(decision,payload=canonical(modified)),'forged','v0')
    file.write_bytes(b'tampered')
    with pytest.raises((ValueError,PermissionError)):gate.authorize(decision,'v1','v0')

def test_verifier_cannot_promote_its_own_attestation(promotion_authority):
    gate,issue,_=promotion_authority;decision=issue()
    with pytest.raises(PermissionError):gate.authorize(replace(decision,approval=decision.verification),'v1','v0')
