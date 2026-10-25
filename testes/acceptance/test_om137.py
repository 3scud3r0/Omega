"""OM-137: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_bench.programming import ProgrammingTask,ProgrammingOracle

def test_hidden_programming_suite_requires_exact_digest_and_sandbox():
    task=ProgrammingTask('p','python','add',((1,2,3),),'a'*64)
    assert 'hidden_suite_digest' not in task.public()['input']
    oracle=ProgrammingOracle([task],lambda *args:{'suite_sha256':'a'*64,'passed':True,'sandboxed':False})
    assert oracle.verify('p','candidate') is False
    wrong=ProgrammingOracle([task],lambda *args:{'suite_sha256':'b'*64,'passed':True,'sandboxed':True})
    with pytest.raises(ValueError):wrong.verify('p','candidate')
