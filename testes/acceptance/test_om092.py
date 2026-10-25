"""OM-092: executable checks; source delivery, not a recorded pass."""
import torch
from torch import nn
from omega_nextorch.capacity import prune_weights

def test_pruning_operates_on_copy_and_does_not_claim_structural_speedup():
    model=nn.Linear(4,2,bias=False)
    with torch.no_grad():model.weight.copy_(torch.arange(1,9).reshape(2,4))
    candidate,record=prune_weights(model,.5)
    assert record['pruned']==4 and record['structural_speedup_claimed'] is False
    assert torch.count_nonzero(candidate.weight)==4 and torch.count_nonzero(model.weight)==8
