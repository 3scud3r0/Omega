import json

import pytest
import torch

from nextorch import ManifoldAnalyzer
from nextorch.model import NextorchModel
from nextorch.synthesis import Architecture, GFlowNetSynthesizer, GraphNode, JITCompiler
from nextorch.synthesis.space import DiagonalSSM, LinearAttention


@pytest.mark.parametrize("op", ["mlp", "ssm", "linear_attention"])
@pytest.mark.parametrize("sequence", [False, True])
def test_dag_primitives_shapes_gradients_and_serialization(op, sequence):
    architecture = Architecture(3, 2, 8, (GraphNode(op, (0,)), GraphNode("mlp", (0, 1))))
    assert Architecture.from_dict(json.loads(json.dumps(architecture.to_dict()))) == architecture
    model = architecture.build()
    x = torch.randn((4, 5, 3) if sequence else (4, 3), requires_grad=True)
    y = model(x)
    assert y.shape == (4, 2)
    y.square().sum().backward()
    assert torch.isfinite(x.grad).all() and x.grad.abs().sum() > 0


def test_space_rejects_forward_edges_and_unsupported_operations():
    with pytest.raises(ValueError):
        Architecture(3, 2, 8, (GraphNode("mlp", (1,)),))
    with pytest.raises(ValueError):
        Architecture(3, 2, 8, (GraphNode("magic", (0,)),))


def test_ssm_is_causal_and_linear_attention_is_permutation_equivariant():
    x = torch.randn(2, 5, 8)
    ssm = DiagonalSSM(8)
    altered = x.clone()
    altered[:, 3:] += 100
    torch.testing.assert_close(ssm(x)[:, :3], ssm(altered)[:, :3])
    attention = LinearAttention(8)
    permutation = torch.tensor([2, 3, 0, 4, 1])
    torch.testing.assert_close(attention(x[:, permutation]), attention(x)[:, permutation])


def test_gflownet_policy_is_trained_and_synthesis_has_real_reward():
    signature = ManifoldAnalyzer.compute_spectral_signature(torch.randn(40, 5))
    synth = GFlowNetSynthesizer(max_depth=3, width=8)
    before = [p.detach().clone() for p in synth.parameters()]
    optimizer = torch.optim.Adam(synth.parameters(), lr=0.01)
    for _ in range(3):
        metrics = synth.train_step(signature, 2, optimizer, batch_size=3)
        assert metrics["loss"] >= 0 and metrics["mean_reward"] > 0
    assert any(not torch.equal(a, b) for a, b in zip(before, synth.parameters()))
    result = synth.synthesize(signature, 2, candidates=3)
    assert result.diagnostics["viable"] and result.model(torch.randn(4, 5)).shape == (4, 2)
    assert 1 <= len(result.architecture.nodes) <= 3


def test_tabular_model_joint_training_reduces_loss():
    x = torch.randn(64, 3)
    labels = (x[:, 0] > 0).long()
    model = NextorchModel.from_tensor(x, 2, width=16, candidates=2)
    initial = torch.nn.functional.cross_entropy(model(x), labels).item()
    history = model.fit(x, labels, epochs=100, lr=0.03)
    final = torch.nn.functional.cross_entropy(model(x), labels).item()
    assert final < initial * 0.5
    assert (model(x).argmax(-1) == labels).float().mean() > 0.9
    assert len(history) == 100 and model.trained_steps == 100
    assert model.sae.encoder.weight.grad is not None


def test_optional_compilation_matches_eager():
    model = torch.nn.Sequential(torch.nn.Linear(3, 4), torch.nn.GELU(), torch.nn.Linear(4, 2))
    x = torch.randn(2, 3)
    compiled = JITCompiler.compile(model, x, backend="aot_eager")
    torch.testing.assert_close(compiled(x), model(x))
    compiled(x).sum().backward()
    assert model[0].weight.grad.abs().sum() > 0
    values, residual = torch.randn(4, 8), torch.randn(4, 8)
    result = JITCompiler.fused_residual_rmsnorm(values, residual)
    torch.testing.assert_close(result.square().mean(-1), torch.ones(4), atol=1e-4, rtol=1e-4)
    with pytest.raises(RuntimeError, match="CUDA"):
        JITCompiler.fused_residual_rmsnorm(values, residual, backend="triton")


@pytest.mark.gpu
@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA device unavailable")
def test_triton_fused_matches_torch():
    pytest.importorskip("triton")
    x, r = torch.randn(5, 33, device="cuda"), torch.randn(5, 33, device="cuda")
    torch.testing.assert_close(
        JITCompiler.fused_residual_rmsnorm(x, r, backend="triton"),
        JITCompiler.fused_residual_rmsnorm(x, r),
        atol=1e-5,
        rtol=1e-5,
    )


def test_tabular_regression_and_unlabelled_learning():
    x = torch.randn(24, 2)
    target = x.sum(-1)
    model = NextorchModel.from_tensor(x, 1, width=8, candidates=1)
    initial = (model(x).squeeze(-1) - target).square().mean().item()
    model.fit(x, target, epochs=120, task="regression", lr=0.03)
    assert (model(x).squeeze(-1) - target).square().mean().item() < initial * 0.3
    assert len(model.fit(x, epochs=2)) == 2
