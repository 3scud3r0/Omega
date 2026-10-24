import pytest
import torch

from nextorch import ManifoldAnalyzer, NextorchConfig
from nextorch.core.tensor import require_matrix, standardize


def test_spectrum_finds_low_rank_and_samples_all_classes():
    x = torch.randn(1000, 2) @ torch.randn(2, 20)
    labels = torch.cat((torch.zeros(990), torch.ones(10)))
    result = ManifoldAnalyzer.compute_spectral_signature(x, labels=labels, max_samples=32)
    assert result["intrinsic_dim"] == 2
    assert len(result["sample_indices"]) == 32
    assert set(labels[result["sample_indices"]].tolist()) == {0, 1}
    again = ManifoldAnalyzer.compute_spectral_signature(x, labels=labels, max_samples=32)
    assert torch.equal(result["sample_indices"], again["sample_indices"])
    assert result["explained_variance"][-1] == pytest.approx(1)


@pytest.mark.parametrize("shape", [(1, 4), (10, 3)])
def test_degenerate_spectrum_is_zero_not_nan(shape):
    result = ManifoldAnalyzer.compute_spectral_signature(torch.ones(shape))
    assert result["intrinsic_dim"] == 0
    assert torch.isfinite(result["explained_variance"]).all()


@pytest.mark.parametrize("x", [torch.empty(0, 3), torch.ones(3), torch.tensor([[float("nan")]])])
def test_matrix_contract_rejects_bad_data(x):
    with pytest.raises(ValueError):
        require_matrix(x)


def test_standardize_constant_columns_and_ints():
    x, mean, scale = standardize(torch.tensor([[1, 2], [1, 4]]))
    assert torch.isfinite(x).all()
    assert x[:, 0].abs().sum() == 0
    torch.testing.assert_close(x * scale + mean, torch.tensor([[1.0, 2.0], [1.0, 4.0]]))


@pytest.mark.parametrize(
    "kwargs",
    [{"d_model": 0}, {"vocab_size": 2}, {"target_l0": 300}, {"learning_rate": float("nan")}],
)
def test_config_validation(kwargs):
    with pytest.raises(ValueError):
        NextorchConfig(**kwargs)
