"""Trainable continuous recurrence and branching, per-sample latent beam search."""

import math
from dataclasses import dataclass

import torch
from torch import nn

from nextorch.verifier.mup import MuPScaleCoordinator

from .dynamic_depth import EntropyExit


@dataclass
class BeamResult:
    logits: torch.Tensor
    uncertainty: torch.Tensor
    trajectory: torch.Tensor  # [steps + 1, batch, width], including h0
    steps: torch.Tensor
    beam_scores: torch.Tensor


class LatentThoughtBlock(nn.Module):
    def __init__(self, d_model):
        super().__init__()
        self.state_gate = nn.Linear(2 * d_model, d_model)
        self.candidate_transform = nn.Sequential(
            nn.Linear(2 * d_model, d_model), nn.GELU(), nn.Linear(d_model, d_model)
        )
        self.layer_norm = nn.LayerNorm(d_model)

    def forward(self, h, context):
        combined = torch.cat((h, context), -1)
        gate = torch.sigmoid(self.state_gate(combined))
        return self.layer_norm(h.lerp(torch.tanh(self.candidate_transform(combined)), gate))


class NextorchReasoner(nn.Module):
    def __init__(self, vocab_size=16, d_model=64, thought_steps=4, max_length=128):
        super().__init__()
        if min(vocab_size, d_model, thought_steps, max_length) <= 0:
            raise ValueError("All reasoner dimensions must be positive")
        self.vocab_size, self.d_model, self.thought_steps = vocab_size, d_model, thought_steps
        self.max_length = max_length
        # One extra symbol is reserved for padding, never a logical proposition.
        self.embedding = nn.Embedding(vocab_size + 1, d_model, padding_idx=vocab_size)
        self.input_layer = nn.Linear(d_model, d_model)
        self.thought_cell = LatentThoughtBlock(d_model)
        self.value_head = nn.Linear(d_model, 1)
        self.policy_head = nn.Linear(d_model, vocab_size)
        position = torch.arange(max_length).float()[:, None]
        freq = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000) / d_model))
        encoding = torch.zeros(max_length, d_model)
        encoding[:, 0::2] = torch.sin(position * freq)
        encoding[:, 1::2] = torch.cos(position * freq[: d_model // 2])
        self.register_buffer("position_encoding", encoding)
        MuPScaleCoordinator.apply_mup_coordinates(self, d_model)
        with torch.no_grad():
            self.embedding.weight[vocab_size].zero_()

    def embed(self, tokens):
        if tokens.ndim != 2 or tokens.shape[1] == 0 or tokens.shape[1] > self.max_length:
            raise ValueError("Expected [batch, nonempty sequence] within max_length")
        if tokens.dtype not in (torch.int32, torch.int64):
            raise TypeError("Token indices must be integers")
        mask = tokens != self.vocab_size
        if not mask.any(-1).all():
            raise ValueError("A sequence cannot consist entirely of padding")
        values = self.embedding(tokens) + self.position_encoding[: tokens.shape[1]]
        # Position-dependent gates preserve order; simple mean pooling would lose edge directions.
        gate = torch.sigmoid(self.position_encoding[: tokens.shape[1]])
        context = (values * gate * mask[..., None]).sum(1) / mask.sum(1, keepdim=True)
        return torch.tanh(self.input_layer(context))

    def forward_embeddings(self, h0, capture_trajectory=False):
        h, trajectory = h0, []
        for _ in range(self.thought_steps):
            h = self.thought_cell(h, h0)
            trajectory.append(h)
        output = (self.policy_head(h), nn.functional.softplus(self.value_head(h)))
        return (*output, trajectory) if capture_trajectory else output

    def forward(self, x, capture_trajectory=False):
        return self.forward_embeddings(self.embed(x), capture_trajectory)

    @torch.no_grad()
    def beam_search(
        self,
        tokens,
        beam_width=4,
        branches=2,
        noise_std=0.05,
        entropy_threshold=0.15,
        min_steps=1,
        growth_limit=4.0,
        generator=None,
    ):
        if min(beam_width, branches) <= 0 or noise_std < 0 or growth_limit <= 1:
            raise ValueError("Invalid beam search configuration")
        h0 = self.embed(tokens)
        batch, width = h0.shape
        h = h0[:, None, :]
        scores = h0.new_zeros(batch, 1)
        previous = nn.functional.softplus(self.value_head(h)).squeeze(-1)
        histories = h.unsqueeze(2)  # [batch, beam, time, width]
        done = torch.zeros(batch, dtype=torch.bool, device=h.device)
        steps = torch.full((batch,), self.thought_steps, device=h.device, dtype=torch.long)
        exit_gate = EntropyExit(entropy_threshold, min_steps)
        for step in range(1, self.thought_steps + 1):
            parents = h.shape[1]
            expanded = h[:, :, None, :].expand(-1, -1, branches, -1)
            context = h0[:, None, None, :].expand_as(expanded)
            candidate = self.thought_cell(expanded, context)
            noise = torch.randn(
                candidate.shape, device=h.device, dtype=h.dtype, generator=generator
            )
            candidate = candidate + noise * noise_std
            candidate = torch.where(done[:, None, None, None], expanded, candidate)
            uncertainty = nn.functional.softplus(self.value_head(candidate)).squeeze(-1)
            cost = scores[:, :, None] + uncertainty
            cost = torch.where(done[:, None, None], scores[:, :, None].expand_as(cost), cost)
            bad = uncertainty > previous[:, :, None] * growth_limit
            cost = cost.masked_fill(bad & ~done[:, None, None], torch.inf)
            flat = cost.flatten(1)
            # Always retain a finite fallback when every branch violates the pruning threshold.
            all_bad = ~torch.isfinite(flat).any(-1)
            flat = torch.where(
                all_bad[:, None], (scores[:, :, None] + uncertainty).flatten(1), flat
            )
            count = min(beam_width, parents * branches)
            scores, indices = flat.topk(count, largest=False, dim=1)
            chosen = indices // branches
            h = candidate.flatten(1, 2).gather(1, indices[..., None].expand(-1, -1, width))
            previous = uncertainty.flatten(1).gather(1, indices)
            histories = histories.gather(1, chosen[..., None, None].expand(-1, -1, step, width))
            histories = torch.cat((histories, h.unsqueeze(2)), dim=2)
            newly_done = exit_gate(self.policy_head(h[:, 0]), step) & ~done
            steps[newly_done] = step
            done |= newly_done
            if done.all():
                break
        best = h[:, 0]
        return BeamResult(
            self.policy_head(best),
            nn.functional.softplus(self.value_head(best)),
            histories[:, 0].transpose(0, 1),
            steps,
            scores,
        )


class ContinuousReasoner(nn.Module):
    """Continuous wrapper for Jacobian/SynFlow diagnostics of a discrete reasoner."""

    def __init__(self, reasoner):
        super().__init__()
        self.thought_cell = reasoner.thought_cell
        self.policy_head = reasoner.policy_head
        self.thought_steps = reasoner.thought_steps

    def forward(self, h):
        context = h
        for _ in range(self.thought_steps):
            h = self.thought_cell(h, context)
        return self.policy_head(h)
