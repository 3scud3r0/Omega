"""OM-078: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_learning.curriculum import Curriculum

def test_curriculum_moves_only_after_verified_observation_window():
    curriculum=Curriculum(['easy','hard'],minimum=2)
    assert curriculum.observe(True)=='easy' and curriculum.observe(True)=='hard'
    assert curriculum.observe(False)=='hard' and curriculum.observe(False)=='easy'
    with pytest.raises(ValueError):curriculum.observe(1)
