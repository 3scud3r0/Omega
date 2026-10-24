import pytest
import torch

from nextorch.engine import NextorchReasoner
from nextorch.engine.dynamic_depth import normalized_entropy
from nextorch.interpretability import FeatureVocabulary, IntegratedSAE, SparsityPID


def test_reasoner_gradients_reach_recurrence_value_and_embedding():
    model = NextorchReasoner(8, 12, 3)
    logits, uncertainty, trajectory = model(torch.tensor([[0, 1, 2], [3, 4, 5]]), True)
    assert logits.shape == (2, 8) and uncertainty.shape == (2, 1)
    assert len(trajectory) == 3 and (uncertainty > 0).all()
    (logits.square().sum() + uncertainty.sum()).backward()
    for name in ["embedding.weight", "thought_cell.state_gate.weight", "value_head.weight"]:
        assert dict(model.named_parameters())[name].grad.abs().sum() > 0


def test_order_and_padding_have_the_correct_semantics():
    model = NextorchReasoner(8, 16, 2)
    a = model.embed(torch.tensor([[0, 1, 2]]))
    b = model.embed(torch.tensor([[2, 1, 0]]))
    assert not torch.allclose(a, b)
    torch.testing.assert_close(a, model.embed(torch.tensor([[0, 1, 2, 8, 8]])))
    with pytest.raises(TypeError):
        model(torch.zeros(2, 3))
    with pytest.raises(ValueError, match="padding"):
        model(torch.full((1, 3), 8))


def test_beam_branching_reproducibility_and_single_sample_matches_batch():
    model = NextorchReasoner(8, 12, 4).eval()
    tokens = torch.tensor([[0, 1, 2], [3, 4, 5]])
    args = dict(beam_width=4, branches=3, entropy_threshold=0, noise_std=0.1)
    a = model.beam_search(tokens, generator=torch.Generator().manual_seed(22), **args)
    b = model.beam_search(tokens, generator=torch.Generator().manual_seed(22), **args)
    torch.testing.assert_close(a.logits, b.logits)
    assert a.trajectory.shape == (5, 2, 12)
    assert a.beam_scores.shape == (2, 4)
    assert torch.isfinite(a.beam_scores).all()
    no_noise = model.beam_search(tokens, noise_std=0, entropy_threshold=0)
    for i in range(2):
        alone = model.beam_search(tokens[i : i + 1], noise_std=0, entropy_threshold=0)
        torch.testing.assert_close(no_noise.logits[i : i + 1], alone.logits)
    greedy_logits = model(tokens)[0]
    torch.testing.assert_close(no_noise.logits, greedy_logits)


def test_beam_early_exit_and_pruning_fallback():
    model = NextorchReasoner(8, 8, 4)
    tokens = torch.tensor([[0, 1, 2]])
    result = model.beam_search(tokens, entropy_threshold=1, min_steps=2)
    assert result.steps.item() == 2 and result.trajectory.shape[0] == 3
    result = model.beam_search(tokens, growth_limit=1.00001, noise_std=10)
    assert torch.isfinite(result.logits).all() and torch.isfinite(result.beam_scores[:, 0]).all()
    torch.testing.assert_close(normalized_entropy(torch.zeros(2, 4)), torch.ones(2))


@pytest.mark.parametrize("mode", ["topk", "jumprelu"])
def test_sae_reconstruction_gradients_and_normalization(mode):
    sae = IntegratedSAE(8, 32, 4, mode=mode)
    x = torch.randn(6, 8, requires_grad=True)
    reconstructed, features = sae(x)
    if mode == "topk":
        assert ((features != 0).sum(-1) <= 4).all()
    sae.compute_loss(x, reconstructed, features).backward()
    assert x.grad.abs().sum() > 0 and sae.encoder.weight.grad.abs().sum() > 0
    with torch.no_grad():
        sae.decoder.weight[:, 0] = 0
    sae.normalize_decoder()
    torch.testing.assert_close(sae.decoder.weight.norm(dim=0), torch.ones(32))
    restored = IntegratedSAE(8, 32, 4, mode=mode)
    restored.load_state_dict(sae.state_dict())
    assert restored.pid.state_dict() == sae.pid.state_dict()


def test_sae_can_fit_a_fixed_latent_batch():
    sae = IntegratedSAE(4, 32, 8)
    x = torch.randn(16, 4)
    optimizer = torch.optim.Adam(sae.parameters(), lr=0.02)
    initial = (sae(x)[0] - x).square().mean().item()
    for _ in range(80):
        optimizer.zero_grad()
        reconstructed, features = sae(x)
        loss = sae.compute_loss(x, reconstructed, features)
        loss.backward()
        optimizer.step()
        sae.normalize_decoder()
    assert (sae(x)[0] - x).square().mean().item() < initial * 0.3


def test_pid_direction_bounds_and_unannotated_vocabulary():
    pid = SparsityPID(target=4)
    original = pid.coefficient
    assert pid.update(20) > original
    for _ in range(10000):
        pid.update(100)
    assert pid.coefficient == pid.maximum
    assert abs(pid.integral) <= pid.integral_limit
    for _ in range(10000):
        pid.update(0)
    assert pid.coefficient == pid.minimum
    with pytest.raises(ValueError):
        pid.update(float("nan"))
    vocab = FeatureVocabulary({2: "user-labelled feature"})
    result = vocab.decode(torch.tensor([[0.0, 1.0, 3.0], [0.0, 0.0, 0.0]]))
    assert result[0][0]["label"] == "user-labelled feature" and result[1] == []
    assert "unannotated" in result[0][1]["label"]
