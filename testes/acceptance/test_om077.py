"""OM-077: executable checks; source delivery, not a recorded pass."""
from omega_learning.forgetting import ForgettingMonitor

def test_forgetting_is_relative_to_best_previous_skill():
    monitor=ForgettingMonitor();monitor.observe('v1',{'math':.8,'code':.5})
    result=monitor.observe('v2',{'math':.6,'code':.9})
    assert abs(result['forgetting']['math']-.2)<1e-9 and result['forgetting']['code']==0
    assert len(monitor.history)==2
