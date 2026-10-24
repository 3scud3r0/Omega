"""Diagnostic proxies evaluated on a copy; caller weights, gradients and modes survive."""

import copy
import math

import torch
from torch import nn


def _output(value):
    return value[0] if isinstance(value, tuple) else value


def _setup(model, shape):
    if not shape or min(shape) <= 0:
        raise ValueError("input_shape must be positive")
    cloned = copy.deepcopy(model).eval()
    param = next(cloned.parameters(), None)
    device = param.device if param is not None else torch.device("cpu")
    dtype = param.dtype if param is not None else torch.float32
    if any(isinstance(m, nn.Embedding) for m in cloned.modules()):
        raise ValueError("Embedding indices are discrete; pass a continuous embedding wrapper")
    return cloned, device, dtype


class ZeroCostVerifier:
    @staticmethod
    def check_dynamic_isometry(model, input_shape):
        cloned, device, dtype = _setup(model, input_shape)
        with torch.enable_grad():
            x = torch.randn(input_shape, device=device, dtype=dtype, requires_grad=True)
            out = _output(cloned(x))
            vector = torch.randn_like(out)
            grad = torch.autograd.grad(out, x, vector)[0]
        return float(grad.norm() / vector.norm().clamp_min(1e-12))

    @staticmethod
    def jacobian_spectrum(model, sample, *, max_elements=65536):
        """Exact singular values of a small continuous sample's Jacobian."""
        cloned, _, _ = _setup(model, sample.shape)
        with torch.enable_grad():
            if sample.numel() * _output(cloned(sample)).numel() > max_elements:
                raise ValueError("Jacobian too large; use the norm proxy or a smaller sample")
            jacobian = torch.autograd.functional.jacobian(lambda x: _output(cloned(x)), sample)
            matrix = jacobian.reshape(-1, sample.numel())
            return torch.linalg.svdvals(matrix).detach()

    @staticmethod
    def compute_synflow(model, input_shape):
        cloned, device, dtype = _setup(model, input_shape)
        with torch.no_grad():
            for p in cloned.parameters():
                p.abs_()
        with torch.enable_grad():
            out = _output(cloned(torch.ones(input_shape, device=device, dtype=dtype)))
            params = [p for p in cloned.parameters() if p.requires_grad]
            if not params:
                return 0.0
            grads = torch.autograd.grad(out.sum(), params, allow_unused=True)
            score = sum(float((p * g).abs().sum()) for p, g in zip(params, grads) if g is not None)
        return score

    @staticmethod
    def compute_snip(model, inputs, targets, loss_fn=None):
        cloned = copy.deepcopy(model).eval()
        params = [p for p in cloned.parameters() if p.requires_grad]
        with torch.enable_grad():
            loss = (loss_fn or nn.functional.cross_entropy)(_output(cloned(inputs)), targets)
            grads = torch.autograd.grad(loss, params, allow_unused=True)
            return sum(float((p * g).abs().sum()) for p, g in zip(params, grads) if g is not None)

    @staticmethod
    def evaluate(model, input_shape):
        flow = ZeroCostVerifier.compute_synflow(model, input_shape)
        ratio = ZeroCostVerifier.check_dynamic_isometry(model, input_shape)
        return {
            "synflow": flow,
            "isometry_ratio": ratio,
            "viable": math.isfinite(flow) and flow > 0 and math.isfinite(ratio) and ratio > 0,
        }
