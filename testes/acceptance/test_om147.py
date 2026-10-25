"""OM-147: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_platform.content_cache import ContentCache

def test_content_addressed_cache_rechecks_bytes_and_refuses_path_addresses(tmp_path):
    cache=ContentCache(tmp_path,max_bytes=1024);key=cache.put(b'proof')
    assert cache.put(b'proof')==key and cache.get(key)==b'proof'
    (tmp_path/key).write_bytes(b'forged')
    with pytest.raises(ValueError):cache.get(key)
    with pytest.raises(ValueError):cache.get('../secret')
