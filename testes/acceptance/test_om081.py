"""OM-081: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_learning.transfer import evaluate,gains

def test_transfer_rejects_training_overlap_and_compares_paired_domains():
    result=evaluate('model',{'new':[1,2]},lambda model,cases:len(cases),['old'])
    assert result=={'new':2} and gains({'new':1},result)=={'new':1}
    with pytest.raises(ValueError):evaluate('m',{'old':[]},lambda *_:1,['old'])
