"""OM-046: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_agent.calibration import metrics

def test_calibration_reports_known_brier_and_rejects_nonfinite_probabilities():
    result=metrics([0,1],[0,1],bins=2)
    assert result['brier']==0 and result['ece']==0 and result['samples']==2
    assert metrics([.5,.5],[0,1],bins=1)['brier']==.25
    with pytest.raises(ValueError):metrics([float('nan')],[1])
