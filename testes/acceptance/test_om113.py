"""OM-113: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_evolution.lineage import Lineage,Version

def test_version_genealogy_requires_known_parents_and_preserves_ancestry():
    lineage=Lineage();lineage.add(Version('v0',(),'e0','a'*64));lineage.add(Version('v1',('v0',),'e1','b'*64))
    assert lineage.ancestors('v1')==('v0','v1')
    with pytest.raises(ValueError):lineage.add(Version('v2',('missing',),'e2','c'*64))
