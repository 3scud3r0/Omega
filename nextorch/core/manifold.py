"""Bounded, reproducible spectral fingerprinting; no supervised training."""

import torch

from .tensor import require_matrix


class ManifoldAnalyzer:
    @staticmethod
    @torch.no_grad()
    def compute_spectral_signature(x, labels=None, *, max_samples=512, variance=0.95, seed=42):
        x = require_matrix(x)
        if max_samples < 2 or not 0 < variance <= 1:
            raise ValueError("max_samples >= 2 and 0 < variance <= 1 required")
        n, d = x.shape
        generator = torch.Generator().manual_seed(seed)
        if labels is not None:
            labels = torch.as_tensor(labels).detach().cpu().reshape(-1)
            if len(labels) != n:
                raise ValueError("labels and samples must have the same length")
            # Round-robin strata, shuffled within each class, then fill to the cap.
            groups = []
            for label in labels.unique():
                group = torch.where(labels == label)[0]
                groups.append(group[torch.randperm(len(group), generator=generator)])
            order = []
            for j in range(max(map(len, groups), default=0)):
                order.extend(int(g[j]) for g in groups if j < len(g))
                if len(order) >= min(n, max_samples):
                    break
            indices = torch.tensor(order[:max_samples], dtype=torch.long)
            if indices.numel() == 0:
                raise ValueError("No usable strata")
        else:
            indices = torch.randperm(n, generator=generator)[:max_samples]
        batch = x[indices.to(x.device)].double()
        singular = torch.linalg.svdvals(batch - batch.mean(0))
        energy = singular.square()
        total = energy.sum()
        if total <= torch.finfo(energy.dtype).eps:
            intrinsic, cumulative, decay = 0, torch.zeros_like(energy), 0.0
        else:
            cumulative = energy.cumsum(0) / total
            intrinsic = min(int(torch.searchsorted(cumulative, variance)) + 1, len(singular))
            decay = float(singular[0] / singular[-1].clamp_min(1e-12))
        return {
            "n_samples": n,
            "input_dim": d,
            "intrinsic_dim": intrinsic,
            "spectral_decay": decay,
            "singular_values": singular.cpu(),
            "explained_variance": cumulative.cpu(),
            "sample_indices": indices,
        }
