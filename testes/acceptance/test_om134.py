"""OM-134: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_security.anomalies import Monitor

def test_monitor_blocks_after_anomaly_and_rejects_nonfinite_measurements():
    monitor=Monitor({'cost':10})
    assert monitor.observe({'cost':5})==() and not monitor.blocked
    alert=monitor.observe({'cost':11})[0]
    assert alert.action=='block_and_review' and monitor.blocked
    with pytest.raises(ValueError):monitor.observe({'cost':float('nan')})
