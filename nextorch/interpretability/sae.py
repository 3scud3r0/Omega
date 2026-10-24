"""Integrated sparse autoencoder with TopK or straight-through JumpReLU gates."""

import torch
from torch import nn

from .pid_sparsity import SparsityPID


class IntegratedSAE(nn.Module):
    def __init__(self, d_model=64, n_features=256, target_l0=8, mode="topk", threshold=0.1):
        super().__init__()
        if min(d_model, n_features, target_l0) <= 0 or target_l0 > n_features:
            raise ValueError("Invalid SAE dimensions/target")
        if mode not in ("topk", "jumprelu") or threshold < 0:
            raise ValueError("Unknown SAE activation or negative threshold")
        self.d_model, self.n_features = d_model, n_features
        self.target_l0, self.mode, self.threshold = int(target_l0), mode, threshold
        self.b_dec = nn.Parameter(torch.zeros(d_model))
        self.encoder = nn.Linear(d_model, n_features)
        self.decoder = nn.Linear(n_features, d_model, bias=False)
        self.pid = SparsityPID(target=float(target_l0))
        self.normalize_decoder()

    @property
    def l1_coeff(self):
        return self.pid.coefficient

    @torch.no_grad()
    def normalize_decoder(self):
        weights = self.decoder.weight
        norms = weights.norm(dim=0, keepdim=True)
        dead = norms.squeeze(0) < 1e-12
        if dead.any():
            weights[:, dead] = torch.randn_like(weights[:, dead])
        weights.div_(weights.norm(dim=0, keepdim=True).clamp_min(1e-12))

    def forward(self, x):
        if x.shape[-1] != self.d_model:
            raise ValueError("SAE input width mismatch")
        activations = self.encoder(x - self.b_dec).relu()
        if self.mode == "topk":
            values, indices = activations.topk(self.target_l0, dim=-1)
            features = torch.zeros_like(activations).scatter(-1, indices, values)
        else:
            hard = (activations > self.threshold).to(activations.dtype)
            # Smooth surrogate gradient, with an exactly hard forward pass.
            soft = torch.sigmoid((activations - self.threshold) * 10)
            gate = hard + soft - soft.detach()
            features = activations * gate
        return self.decoder(features) + self.b_dec, features

    def update_pid(self, current_l0):
        return self.pid.update(current_l0)

    def compute_loss(self, x, x_recon, features, *, update_pid=True):
        if update_pid:
            self.update_pid(float((features.detach() != 0).sum(-1).float().mean()))
        reconstruction = nn.functional.mse_loss(x_recon, x)
        return reconstruction + self.l1_coeff * features.abs().sum(-1).mean()

    def get_extra_state(self):
        return self.pid.state_dict()

    def set_extra_state(self, state):
        self.pid = SparsityPID(**state)
