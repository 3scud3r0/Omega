"""OM-055: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_agent.domain_shift import DomainShift

def test_unknown_distribution_abstains_only_after_calibration():
    detector=DomainShift([[0],[1],[2]])
    with pytest.raises(ValueError):detector.abstain([100])
    detector.calibrate([[0],[1],[2]])
    assert detector.abstain([100]) and not detector.abstain([1])
