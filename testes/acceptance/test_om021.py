"""OM-021: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_platform.scheduler import Job,BatchLimits,admit,execute_reproducible
from omega_platform.budget import Budget

def test_admission_rejects_entire_duplicate_or_overbudget_batch():
    job=Job('a',('/usr/bin/true',),budget=Budget(cpu_seconds=2))
    with pytest.raises(ValueError):admit((job,job))
    with pytest.raises(ValueError):admit((job,),BatchLimits(reserved_cpu_seconds=1))
    with pytest.raises(ValueError):Job('bad',('relative',))

def test_readonly_process_batch_preserves_order_and_repeats():
    jobs=tuple(Job(str(i),('/usr/bin/printf',str(i)),budget=Budget(cpu_seconds=1)) for i in range(3))
    runs=execute_reproducible(jobs,repetitions=2)
    assert [[(id,result.stdout) for id,result in batch] for batch in runs]==[[('0','0'),('1','1'),('2','2')]]*2
    assert all(result.sandboxed for batch in runs for _,result in batch)
