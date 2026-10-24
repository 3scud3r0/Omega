"""Validated runtime configuration. Importing Nextorch does not change global RNG state."""

import random
from dataclasses import dataclass

import numpy as np
import torch


@dataclass(frozen=True)
class NextorchConfig:
    vocab_size: int = 16
    d_model: int = 64
    thought_steps: int = 4
    beam_width: int = 4
    n_features: int = 256
    target_l0: int = 8
    replay_capacity: int = 4096
    learning_rate: float = 1e-3
    seed: int = 42
    device: str = "cpu"
    require_lean: bool = False

    def __post_init__(self):
        for name in (
            "vocab_size",
            "d_model",
            "thought_steps",
            "beam_width",
            "n_features",
            "target_l0",
            "replay_capacity",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.vocab_size < 4 or self.target_l0 > self.n_features:
            raise ValueError("Need vocab_size >= 4 and target_l0 <= n_features")
        if not np.isfinite(self.learning_rate) or self.learning_rate <= 0:
            raise ValueError("learning_rate must be finite and positive")
        if torch.device(self.device).type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but not available")


def seed_everything(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
