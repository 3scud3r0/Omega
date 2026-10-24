"""Per-sample early exit based on normalized predictive entropy."""

import math

import torch


def normalized_entropy(logits):
    if logits.shape[-1] < 2:
        return torch.zeros(logits.shape[:-1], device=logits.device, dtype=logits.dtype)
    logp = logits.log_softmax(-1)
    return -(logp.exp() * logp).sum(-1) / math.log(logits.shape[-1])


class EntropyExit:
    def __init__(self, threshold=0.15, min_steps=1):
        if not 0 <= threshold <= 1 or min_steps < 1:
            raise ValueError("Invalid entropy exit settings")
        self.threshold, self.min_steps = threshold, min_steps

    def __call__(self, logits, step):
        return (normalized_entropy(logits) <= self.threshold) & (step >= self.min_steps)
