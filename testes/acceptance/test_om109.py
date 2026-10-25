"""OM-109: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_evolution.statistics import paired_interval,holm

def test_paired_bootstrap_constant_gain_and_multiple_comparison_control():
    interval=paired_interval([0,0,0],[1,1,1],seed=7,resamples=100)
    assert interval['mean_delta']==1 and interval['ci95']==(1,1)
    assert holm({'strong':.001,'weak':.03,'none':.9})=={'strong':True,'weak':False,'none':False}
    with pytest.raises(ValueError):paired_interval([1],[2],resamples=100)
