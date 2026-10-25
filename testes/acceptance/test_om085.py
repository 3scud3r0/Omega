"""OM-085: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_memory.privacy import PrivacyPolicy

def test_sensitive_retrieval_training_and_expiry_require_consent():
    policy=PrivacyPolicy(lambda owner,principal,purpose,id,consent:consent=='explicit')
    record={'id':'e','owner':'alice','sensitive':True,'expires':None}
    with pytest.raises(PermissionError):policy.require(record,'retrieve','agent',None)
    assert policy.require(record,'train','agent','explicit')
    with pytest.raises(PermissionError):policy.require({**record,'expires':1},'retrieve','agent','explicit')
