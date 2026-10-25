"""OM-091: executable checks; source delivery, not a recorded pass."""
import torch
from torch import nn
import pytest
from nextorch.evolution.net2net import Net2NetExpansion

@pytest.mark.parametrize('activation',[nn.ReLU,nn.Tanh])
def test_net2wider_preserves_outputs_and_input_gradients(activation):
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(7);model=nn.Sequential(nn.Linear(2,3),activation(),nn.Linear(3,1)).double()
        inputs=torch.randn(4,2,dtype=torch.double,requires_grad=True)
        before=model(inputs);gradient=torch.autograd.grad(before.sum(),inputs)[0]
        grown=Net2NetExpansion.widen_sequential(model,0,7,torch.Generator().manual_seed(9))
        after=grown(inputs)
        torch.testing.assert_close(after,before,atol=1e-12,rtol=1e-12)
        torch.testing.assert_close(torch.autograd.grad(after.sum(),inputs)[0],gradient,atol=1e-12,rtol=1e-12)
