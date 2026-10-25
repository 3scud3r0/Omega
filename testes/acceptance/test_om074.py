"""OM-074: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_memory.lifecycle import Lifecycle

def test_memory_versions_deduplicate_expire_and_return_copies():
    memory=Lifecycle();first=memory.add('k',{'value':1});assert memory.add('k',{'value':1})==first
    second=memory.add('k',{'value':2},expires=10)
    assert second!=first and first in memory.obsolete()
    copy=memory.current('k',now=1);copy['value']=9
    assert memory.current('k',now=1)=={'value':2}
    with pytest.raises(PermissionError):memory.current('k',now=10)
