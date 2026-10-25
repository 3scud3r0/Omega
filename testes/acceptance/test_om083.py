"""OM-083: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_learning.data_splits import DataSplits

def test_split_contamination_rejected_by_identity_and_content():
    a={'id':'a','input':{'x':1}};b={'id':'b','input':{'x':2}}
    splits=DataSplits([a],[],[b]);copy=splits.get('train');copy[0]['input']['x']=99
    assert splits.get('train')[0]['input']['x']==1
    with pytest.raises(ValueError):DataSplits([a],[],[{'id':'other','input':{'x':1}}])
    with pytest.raises(ValueError):DataSplits([a],[],[{'id':'a','input':{'x':2}}])
