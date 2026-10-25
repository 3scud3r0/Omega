"""OM-025: executable checks; source delivery, not a recorded pass."""
import hashlib
import pytest
from omega.packages import verify,order

def test_lock_verifies_bytes_and_dependency_order(tmp_path):
    (tmp_path/'base').mkdir();(tmp_path/'app').mkdir();(tmp_path/'base'/'x').write_bytes(b'original')
    lock={'format':'omega-package-lock-1','packages':{'app':{'version':'1.0.0','files':{},'dependencies':['base']},'base':{'version':'1.0.0','files':{'x':hashlib.sha256(b'original').hexdigest()},'dependencies':[]}}}
    assert order(lock)==('base','app') and verify(lock,tmp_path)==('base','app')
    (tmp_path/'base'/'x').write_bytes(b'changed')
    with pytest.raises(ValueError):verify(lock,tmp_path)

def test_cyclic_lock_cannot_be_resolved():
    lock={'format':'omega-package-lock-1','packages':{'a':{'version':'1.0.0','files':{},'dependencies':['a']}}}
    with pytest.raises(ValueError):order(lock)
