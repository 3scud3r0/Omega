"""Small, explicit tensor contracts used at public numerical boundaries."""

import torch


def require_matrix(x: torch.Tensor, *, finite: bool = True) -> torch.Tensor:
    if not isinstance(x, torch.Tensor) or x.ndim != 2 or min(x.shape) == 0:
        raise ValueError("Expected a nonempty [samples, features] tensor")
    if not x.is_floating_point():
        x = x.float()
    if finite and not torch.isfinite(x).all():
        raise ValueError("Tensor contains NaN or infinity; impute missing values first")
    return x


def standardize(x: torch.Tensor):
    x = require_matrix(x)
    mean = x.mean(0)
    scale = x.std(0, unbiased=False).clamp_min(torch.finfo(x.dtype).eps)
    return (x - mean) / scale, mean, scale
