"""Explicit optional compilation. CPU eager execution is always supported."""

import importlib.util

import torch


class JITCompiler:
    @staticmethod
    def compile(model, example, backend="eager"):
        if backend == "eager":
            model(example)  # validate the input contract now
            return model
        if backend not in ("inductor", "aot_eager"):
            raise ValueError("Supported backends: eager, aot_eager, inductor")
        compiled = torch.compile(model, backend=backend)
        expected, actual = model(example), compiled(example)
        torch.testing.assert_close(actual, expected)
        return compiled

    @staticmethod
    def fused_residual_rmsnorm(x, residual, eps=1e-6, *, backend="torch"):
        if x.shape != residual.shape or x.ndim != 2 or eps <= 0:
            raise ValueError("Need equal [batch, width] tensors and positive epsilon")
        if backend == "torch":
            values = x + residual
            return values * torch.rsqrt(values.float().square().mean(-1, keepdim=True) + eps).to(
                x.dtype
            )
        if backend != "triton":
            raise ValueError("Choose torch or triton")
        if not x.is_cuda or not residual.is_cuda:
            raise RuntimeError("Triton fused kernel requires CUDA tensors")
        if importlib.util.find_spec("triton") is None:
            raise RuntimeError("Install nextorch-ai[gpu] for the Triton backend")
        from .triton_kernels import residual_rmsnorm

        return residual_rmsnorm(x, residual, eps)
