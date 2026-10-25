"""OM-076: executable checks; source delivery, not a recorded pass."""
from omega_learning.incremental import update

def test_incremental_training_copies_baseline_and_rejects_retained_regression():
    model={'old':1,'new':0}
    def train(candidate,_):candidate.update(old=0,new=1)
    result=update(model,[],[],train,lambda value,_:{'old':value['old']})
    assert model=={'old':1,'new':0} and result['candidate']['new']==1
    assert not result['accepted_for_review'] and result['regressions']=={'old':-1} and result['promoted'] is False
