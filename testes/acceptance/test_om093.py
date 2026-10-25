"""OM-093: executable checks; source delivery, not a recorded pass."""
import torch
from torch import nn
from omega_nextorch.causal_analysis import intervene

def test_feature_ablation_changes_output_and_removes_hook():
    model=nn.Sequential(nn.Linear(2,2,bias=False),nn.Identity())
    with torch.no_grad():model[0].weight.copy_(torch.eye(2))
    model.train();result=intervene(model[0],model,torch.tensor([[2.,3.]]),0,lambda output:output.sum())
    assert result['baseline']==5 and result['intervention']==3 and result['delta']==-2
    assert model.training and len(model[0]._forward_hooks)==0
