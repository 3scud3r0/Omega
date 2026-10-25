"""OM-063: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_coder.counterexamples import Counterexample,correction_task

def test_counterexample_must_reproduce_before_repair_task_is_emitted():
    example=Counterexample('f'*64,{'x':0},'nonzero','lean')
    task=correction_task(example,lambda assignment:assignment['x']!=0)
    assert task['regression_input']=={'x':0} and task['statement_sha256']=='f'*64
    with pytest.raises(ValueError):correction_task(example,lambda _:True)
