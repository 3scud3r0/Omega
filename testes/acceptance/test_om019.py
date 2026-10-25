"""OM-019: executable checks; source delivery, not a recorded pass."""
from fractions import Fraction
import pytest
from omega.stdlib import RationalQueue,RationalStack,RationalMap

def test_queue_stack_exactness_and_atomic_overflow():
    queue=RationalQueue(2);stack=RationalStack(2)
    for container in (queue,stack):
        container.push(Fraction(1,3));container.push(2)
        with pytest.raises(OverflowError):container.push(9)
        assert container.values()==(Fraction(1,3),Fraction(2))
    assert queue.pop()==Fraction(1,3) and stack.pop()==2

def test_map_overwrite_and_rejected_nonrational_do_not_mutate():
    table=RationalMap(1);table.put('x',1);table.put('x',Fraction(2,3))
    with pytest.raises(OverflowError):table.put('y',2)
    with pytest.raises(TypeError):table.put('x',True)
    assert table.items()==(('x',Fraction(2,3)),)
