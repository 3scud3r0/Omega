"""OM-075: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_memory.certified_replay import CertifiedReplay

def test_replay_deduplicates_evicts_and_rechecks_before_sampling():
    allowed=[True];replay=CertifiedReplay(lambda sample,certificate:allowed[0] and sample==certificate,capacity=1)
    key=replay.add({'x':1},{'x':1});assert replay.add({'x':1},{'x':1})==key
    replay.add({'x':2},{'x':2});assert len(replay.order)==1
    assert replay.sample(1,7)==(({'x':2},{'x':2}),)
    allowed[0]=False
    with pytest.raises(ValueError):replay.sample(1,7)
