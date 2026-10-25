"""OM-062: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_coder.repair import RepairLoop

def test_repair_keeps_required_checks_and_records_failed_attempts():
    loop=RepairLoop(lambda candidate,*_:candidate+1,lambda value:{'compile':value>=2,'regression':True},['compile','regression'])
    result=loop.run(0,'failure',max_attempts=3)
    assert result.accepted and result.candidate==2 and len(result.attempts)==3
    bad=RepairLoop(lambda *_:0,lambda _:{'compile':True},['compile','regression'])
    with pytest.raises(ValueError):bad.run(0,'missing check')
