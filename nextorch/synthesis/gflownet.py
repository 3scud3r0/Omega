"""Trainable trajectory-balance GFlowNet over a bounded canonical DAG family.

Each state has a unique predecessor (remove its last block), so the backward
transition probability is one. Actions choose an operation/skip edge or STOP.
Zero-cost rewards are only heuristic; generated models still need task training.
"""

import math
from dataclasses import dataclass

import torch
from torch import nn

from nextorch.verifier.zerocost import ZeroCostVerifier

from .space import OPERATIONS, Architecture, GraphNode


@dataclass
class SynthesisResult:
    architecture: Architecture
    model: nn.Module
    diagnostics: dict


class GFlowNetSynthesizer(nn.Module):
    def __init__(self, max_depth=4, width=32):
        super().__init__()
        if min(max_depth, width) <= 0:
            raise ValueError("Depth and width must be positive")
        self.max_depth, self.width = max_depth, width
        self.n_actions = len(OPERATIONS) * 2 + 1
        self.policy = nn.Sequential(
            nn.Linear(5 + self.n_actions, 32), nn.Tanh(), nn.Linear(32, self.n_actions)
        )
        self.log_z = nn.Parameter(torch.zeros(()))

    def _context(self, signature):
        return next(self.parameters()).new_tensor(
            [
                math.log1p(signature["input_dim"]) / 10,
                signature["intrinsic_dim"] / max(signature["input_dim"], 1),
                math.log1p(signature["n_samples"]) / 10,
                math.log1p(min(signature["spectral_decay"], 1e6)) / 20,
            ]
        )

    def _sample(self, signature, output_dim, generator=None):
        context = self._context(signature)
        nodes, log_prob = [], context.new_zeros(())
        counts = context.new_zeros(self.n_actions)
        for depth in range(self.max_depth + 1):
            if depth == self.max_depth:
                break  # terminal forced transition contributes log(1)
            state = torch.cat((context, context.new_tensor([depth / self.max_depth]), counts))
            logits = self.policy(state)
            invalid = torch.zeros_like(logits, dtype=torch.bool)
            if depth == 0:
                invalid[-1] = True
                invalid[1:-1:2] = True  # no duplicate skip-to-input action at depth zero
            logits = logits.masked_fill(invalid, -torch.inf)
            probs = logits.softmax(-1)
            action = int(torch.multinomial(probs.detach(), 1, generator=generator))
            log_prob = log_prob + logits.log_softmax(-1)[action]
            if action == self.n_actions - 1:
                break
            op = OPERATIONS[action // 2]
            parents = (depth,) if not action % 2 else (0, depth)
            nodes.append(GraphNode(op, parents))
            counts = counts.clone()
            counts[action] += 1 / self.max_depth
        arch = Architecture(signature["input_dim"], output_dim, self.width, tuple(nodes))
        return arch, log_prob

    def train_step(self, signature, output_dim, optimizer, batch_size=4, generator=None):
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        losses, rewards = [], []
        for _ in range(batch_size):
            architecture, log_pf = self._sample(signature, output_dim, generator)
            model = architecture.build().to(next(self.parameters()).device)
            diagnostics = ZeroCostVerifier.evaluate(model, (2, architecture.input_dim))
            ratio = diagnostics["isometry_ratio"]
            reward = max(
                1e-6,
                math.exp(-abs(math.log(max(ratio, 1e-6))))
                / (1 + sum(p.numel() for p in model.parameters()) / 10000),
            )
            if not diagnostics["viable"]:
                reward = 1e-6
            losses.append((self.log_z + log_pf - math.log(reward)).square())
            rewards.append(reward)
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        return {"loss": float(loss.detach()), "mean_reward": sum(rewards) / len(rewards)}

    def synthesize(self, signature, output_dim=2, candidates=8, generator=None):
        if candidates <= 0:
            raise ValueError("candidates must be positive")
        best = None
        for _ in range(candidates):
            arch, _ = self._sample(signature, output_dim, generator)
            model = arch.build().to(next(self.parameters()).device)
            diagnostics = ZeroCostVerifier.evaluate(model, (2, arch.input_dim))
            if not diagnostics["viable"]:
                continue
            score = abs(math.log(max(diagnostics["isometry_ratio"], 1e-12)))
            diagnostics.update(parameters=sum(p.numel() for p in model.parameters()), score=score)
            if best is None or score < best.diagnostics["score"]:
                best = SynthesisResult(arch, model, diagnostics)
        if best is None:
            raise RuntimeError("All candidate architectures failed zero-cost viability checks")
        return best
