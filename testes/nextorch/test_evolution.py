import json

import pytest
import torch
from torch import nn

from nextorch import NextorchConfig, NextorchEngine
from nextorch.evolution import CertifiedReplayBuffer, Net2NetExpansion
from nextorch.formal import LogicalProblem


@pytest.mark.parametrize("activation", [nn.ReLU, nn.GELU, nn.Tanh, nn.Sigmoid])
@pytest.mark.parametrize("bias", [False, True])
def test_net2wider_preserves_full_function_and_gradients(activation, bias):
    model = nn.Sequential(
        nn.Linear(3, 5, bias=bias), activation(), nn.Linear(5, 2, bias=bias)
    ).double()
    x = torch.randn(20, 3, dtype=torch.double, requires_grad=True)
    expected = model(x)
    expected_grad = torch.autograd.grad(expected.sum(), x)[0]
    grown = Net2NetExpansion.widen_sequential(model, 0, 13)
    actual = grown(x)
    torch.testing.assert_close(actual, expected, rtol=1e-12, atol=1e-12)
    torch.testing.assert_close(
        torch.autograd.grad(actual.sum(), x)[0], expected_grad, rtol=1e-12, atol=1e-12
    )
    assert sum(p.numel() for p in grown.parameters()) > sum(p.numel() for p in model.parameters())
    assert grown[0].weight.dtype == torch.double


def test_net2wider_rejects_layernorm_and_shrinking():
    model = nn.Sequential(nn.Linear(3, 4), nn.LayerNorm(4), nn.Linear(4, 2))
    with pytest.raises(ValueError):
        Net2NetExpansion.widen_sequential(model, 0, 8)
    with pytest.raises(ValueError):
        Net2NetExpansion.widen_pair(model[0], model[2], 2)


def test_replay_rejects_false_deduction_deduplicates_and_evicts(tmp_path):
    replay = CertifiedReplayBuffer(capacity=2)
    problem = LogicalProblem(((0, 1), (1, 2)), 0)
    assert not replay.admit(problem, 3)[0]
    assert len(replay) == 0
    assert replay.admit(problem, 2)[0]
    assert not replay.admit(problem, 2)[0]
    assert replay.admit(problem, 1)[0]
    assert replay.admit(problem, 0)[0]
    assert len(replay) == 2
    replay.save(tmp_path / "replay.json")
    loaded = CertifiedReplayBuffer.load(tmp_path / "replay.json")
    assert [i.target for i in loaded] == [1, 0]
    assert all(item.certificate.proof for item in loaded)


def test_replay_revalidates_even_when_a_serialized_certificate_claims_valid(tmp_path):
    replay = CertifiedReplayBuffer()
    replay.admit(LogicalProblem(((0, 1),), 0), 1)
    payload = replay.to_dict()
    payload["entries"][0]["target"] = 2
    path = tmp_path / "forged.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Uncertified"):
        CertifiedReplayBuffer.load(path)


def _engine():
    return NextorchEngine(
        config=NextorchConfig(vocab_size=8, d_model=12, n_features=48, thought_steps=2)
    )


def test_expert_iteration_certifies_trains_and_can_run_without_expert():
    engine = _engine()
    problems = [LogicalProblem(((0, 1), (1, 2)), 0), LogicalProblem(((3, 4), (4, 5)), 3)]
    before = engine.reasoner.thought_cell.state_gate.weight.detach().clone()
    sae_before = engine.sae.encoder.weight.detach().clone()
    report = engine.execute_self_improvement_cycle(problems=problems)
    assert report.problems == 2 and report.model_accepted + report.model_rejected == 2
    assert report.expert_added >= 1 and report.replay_size >= 2 and report.loss > 0
    assert all(e.certificate.valid for e in engine.replay)
    assert not torch.equal(before, engine.reasoner.thought_cell.state_gate.weight)
    assert not torch.equal(sae_before, engine.sae.encoder.weight)
    next_report = engine.execute_self_improvement_cycle(problems=problems, expert_iteration=False)
    assert next_report.expert_added == 0


def test_expansion_preserves_reasoner_function_and_updates_optimizer():
    engine = _engine()
    tokens = torch.tensor([[0, 1, 2]])
    expected = engine.reasoner(tokens)[0].detach()
    old_count = engine.parameter_count
    assert engine.expand_capacity()
    torch.testing.assert_close(engine.reasoner(tokens)[0], expected)
    assert engine.parameter_count > old_count
    optimized = {id(p) for group in engine.optimizer.param_groups for p in group["params"]}
    assert optimized == {
        id(p) for p in list(engine.reasoner.parameters()) + list(engine.sae.parameters())
    }
    engine.execute_self_improvement_cycle(n_problems=2)
    engine.loss_history = [1.0, 1.0, 1.0]
    assert engine._plateau()


def test_checkpoint_roundtrip_after_growth_preserves_replay_pid_and_predictions(tmp_path):
    engine = _engine()
    engine.execute_self_improvement_cycle(n_problems=3)
    engine.expand_capacity()
    engine.execute_self_improvement_cycle(n_problems=2)
    tokens = torch.tensor([[0, 1, 2]])
    expected = engine.reasoner(tokens)[0].detach()
    path = tmp_path / "checkpoint.pt"
    engine.save_checkpoint(path)
    restored = NextorchEngine.load_checkpoint(path)
    torch.testing.assert_close(restored.reasoner(tokens)[0], expected)
    assert len(restored.replay) == len(engine.replay)
    assert restored.sae.pid.state_dict() == engine.sae.pid.state_dict()
    assert restored.rng.getstate() == engine.rng.getstate()
    assert restored.parameter_count == engine.parameter_count
    assert restored.execute_self_improvement_cycle(n_problems=2).loss is not None
