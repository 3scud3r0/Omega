"""OM-112: executable checks; source delivery, not a recorded pass."""
from omega_evolution.regressions import gate

def test_capability_or_safety_regression_blocks_promotion():
    result=gate({'code':.9},{'code':.8},{'sandbox':True},['sandbox'])
    assert not result['passed'] and ('capability_regression','code') in result['failures']
    assert not gate({'code':1},{'code':1},{},['sandbox'])['passed']
    assert gate({'code':1},{'code':1},{'sandbox':True},['sandbox'])['passed']
