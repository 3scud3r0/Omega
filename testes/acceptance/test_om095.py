"""OM-095: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_nextorch.distributed_training import partition

def test_distributed_partitions_are_disjoint_complete_and_rank_checked():
    parts=[partition(range(11),rank,3) for rank in range(3)]
    assert set().union(*map(set,parts))==set(range(11))
    assert not set(parts[0])&set(parts[1]) and not set(parts[1])&set(parts[2])
    with pytest.raises(ValueError):partition([1,2],3,3)
