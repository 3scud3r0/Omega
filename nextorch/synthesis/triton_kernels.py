"""Inference-only fused residual addition and RMS normalization (optional CUDA)."""

import torch
import triton
import triton.language as tl


@triton.jit
def _rms_kernel(X, R, Y, WIDTH: tl.constexpr, EPS: tl.constexpr, BLOCK: tl.constexpr):
    row = tl.program_id(0)
    cols = tl.arange(0, BLOCK)
    x = tl.load(X + row * WIDTH + cols, cols < WIDTH, other=0).to(tl.float32)
    r = tl.load(R + row * WIDTH + cols, cols < WIDTH, other=0).to(tl.float32)
    values = x + r
    variance = tl.sum(values * values, axis=0) / WIDTH
    tl.store(Y + row * WIDTH + cols, values * tl.rsqrt(variance + EPS), cols < WIDTH)


def residual_rmsnorm(x, residual, eps):
    if x.requires_grad or residual.requires_grad:
        raise ValueError("Fused Triton backend is inference-only; use torch for autograd")
    if x.dtype != residual.dtype or x.dtype not in (torch.float16, torch.bfloat16, torch.float32):
        raise ValueError("Need equal fp16, bf16 or fp32 dtypes")
    x, residual = x.contiguous(), residual.contiguous()
    width = x.shape[1]
    if width == 0 or width > 65536:
        raise ValueError("Triton RMS width must be between 1 and 65536")
    result = torch.empty_like(x)
    _rms_kernel[(x.shape[0],)](x, residual, result, width, eps, triton.next_power_of_2(width))
    return result
