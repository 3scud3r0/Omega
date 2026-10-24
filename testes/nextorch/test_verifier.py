import copy

import pytest
import torch
from torch import nn

from nextorch.engine import ContinuousReasoner, NextorchReasoner
from nextorch.verifier import MuPScaleCoordinator, ZeroCostVerifier
from nextorch.verifier.curvature import dominant_hessian_eigenvalue, hutchinson_trace


def test_synflow_exact_known_linear_chain_and_preserves_state():
    model = nn.Sequential(nn.Linear(2, 2, bias=False), nn.Linear(2, 1, bias=False)).double()
    with torch.no_grad():
        model[0].weight.fill_(-1)
        model[1].weight.fill_(1)
    model.train()
    model[1].eval()
    model(torch.ones(1, 2, dtype=torch.double)).sum().backward()
    state = copy.deepcopy(model.state_dict())
    gradients = [p.grad.clone() for p in model.parameters()]
    assert ZeroCostVerifier.compute_synflow(model, (1, 2)) == pytest.approx(8)
    assert model.training and not model[1].training
    for key, value in model.state_dict().items():
        torch.testing.assert_close(value, state[key])
    for p, gradient in zip(model.parameters(), gradients):
        torch.testing.assert_close(p.grad, gradient)


def test_identity_isometry_and_spectrum():
    model = nn.Linear(3, 3, bias=False)
    with torch.no_grad():
        model.weight.copy_(torch.eye(3))
    assert ZeroCostVerifier.check_dynamic_isometry(model, (2, 3)) == pytest.approx(1)
    torch.testing.assert_close(
        ZeroCostVerifier.jacobian_spectrum(model, torch.ones(1, 3)), torch.ones(3)
    )
    with pytest.raises(ValueError, match="too large"):
        ZeroCostVerifier.jacobian_spectrum(model, torch.ones(1, 3), max_elements=1)


def test_discrete_inputs_have_an_explicit_continuous_diagnostic_path():
    model = NextorchReasoner(8, 8, 2)
    with pytest.raises(ValueError, match="discrete"):
        ZeroCostVerifier.compute_synflow(model, (1, 3))
    result = ZeroCostVerifier.evaluate(ContinuousReasoner(model), (2, 8))
    assert result["viable"] and result["synflow"] > 0


def test_snip_supervised_nonzero():
    model = nn.Linear(2, 2)
    assert ZeroCostVerifier.compute_snip(model, torch.randn(4, 2), torch.tensor([0, 1, 1, 0])) > 0
    assert all(p.grad is None for p in model.parameters())


def test_mup_input_fanin_and_head_coordinates():
    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.input_layer = nn.Linear(4, 2048)
            self.policy_head = nn.Linear(2048, 8)

    model = Net()
    MuPScaleCoordinator.apply_mup_coordinates(model, 2048)
    assert model.input_layer.weight.std().item() == pytest.approx(0.5, rel=0.03)
    assert model.policy_head.weight.std().item() == pytest.approx(1 / 2048, rel=0.03)
    optimizer = MuPScaleCoordinator.optimizer(model, 2048, lr=0.01)
    assert [g["lr"] for g in optimizer.param_groups] == [0.01, 0.01 / 2048]
    assert sum(len(g["params"]) for g in optimizer.param_groups) == len(list(model.parameters()))


def test_hessian_estimators_on_known_quadratic():
    x = nn.Parameter(torch.tensor([1.0, 2.0, 3.0], dtype=torch.double))
    diagonal = torch.tensor([2.0, 4.0, 9.0], dtype=torch.double)
    loss = (x.square() * diagonal).sum() / 2
    assert hutchinson_trace(loss, [x], samples=8) == pytest.approx(15)
    assert dominant_hessian_eigenvalue(loss, [x], iterations=40) == pytest.approx(9, rel=1e-6)
    assert x.grad is None


def test_zero_hessian_and_unused_parameters():
    x, unused = nn.Parameter(torch.ones(2)), nn.Parameter(torch.ones(1))
    assert hutchinson_trace(x.sum(), [x, unused]) == 0
    assert dominant_hessian_eigenvalue(x.sum(), [x, unused]) == 0
