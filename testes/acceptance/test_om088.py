"""OM-088: executable checks; source delivery, not a recorded pass."""
import torch
from torch import nn
from omega_nextorch.supervised_training import train

def test_supervised_training_is_bounded_and_does_not_claim_heldout_results():
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(3);model=nn.Linear(2,2);before=model.weight.detach().clone()
        result=train(model,[(torch.eye(2),torch.tensor([0,1]))]*4,steps=2,learning_rate=.01)
        assert result['steps']==2 and result['heldout_evaluated'] is False
        assert not torch.equal(before,model.weight) and all(torch.isfinite(torch.tensor(loss)) for loss in result['training_loss'])
