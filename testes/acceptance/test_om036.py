"""OM-036: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_platform.proof_cache import ProofCache

def test_proof_cache_rechecks_and_separates_checker_context(tmp_path):
    cache=ProofCache(tmp_path);verify=lambda statement,cert:cert=={'answer':statement}
    cache.store('P','lean-A',['dep'],{'answer':'P'},verify)
    assert cache.lookup('P','lean-A',['dep'],verify)=={'answer':'P'}
    assert cache.lookup('P','lean-B',['dep'],verify) is None
    with pytest.raises(ValueError):cache.lookup('P','lean-A',['dep'],lambda *_:False)
