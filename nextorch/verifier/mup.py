"""Finite-width initialization/LR coordinates from the Nextorch specification.

This recipe is not a proof of asymptotic hyperparameter transfer. Architectural
and optimizer assumptions must be tested before extrapolating to wider networks.
"""

import math

import torch
from torch import nn


class MuPScaleCoordinator:
    @staticmethod
    def apply_mup_coordinates(model, d_model=None):
        if d_model is not None and d_model <= 0:
            raise ValueError("d_model must be positive")
        for name, module in model.named_modules():
            if isinstance(module, nn.Linear):
                std = (
                    1 / module.in_features if "head" in name else 1 / math.sqrt(module.in_features)
                )
                nn.init.normal_(module.weight, std=std)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, std=1.0)

    @staticmethod
    def optimizer(model, d_model, lr=1e-3, weight_decay=1e-4):
        if d_model <= 0 or lr <= 0:
            raise ValueError("Positive width and learning rate required")
        ordinary, readout = [], []
        for name, parameter in model.named_parameters():
            if parameter.requires_grad:
                (readout if "head" in name else ordinary).append(parameter)
        groups = [{"params": ordinary, "lr": lr}, {"params": readout, "lr": lr / d_model}]
        return torch.optim.AdamW(groups, weight_decay=weight_decay)
