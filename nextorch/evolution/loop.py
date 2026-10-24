"""Proof-gated expert iteration with joint reasoner/SAE training and elastic capacity."""

import copy
import os
import random
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import nn

from nextorch.config import NextorchConfig
from nextorch.engine import NextorchReasoner
from nextorch.formal import FormalBarrier, LogicalProblem
from nextorch.interpretability import IntegratedSAE
from nextorch.verifier import MuPScaleCoordinator

from .net2net import Net2NetExpansion
from .replay_buffer import CertifiedReplayBuffer


@dataclass
class CycleReport:
    problems: int
    model_accepted: int
    model_rejected: int
    expert_added: int
    replay_size: int
    loss: float | None
    parameters: int
    expanded: bool
    elapsed_seconds: float
    certified_per_minute: float


class NextorchEngine:
    def __init__(self, vocab_size=16, d_model=64, config=None):
        self.config = config or NextorchConfig(
            vocab_size=vocab_size, d_model=d_model, n_features=d_model * 4
        )
        c = self.config
        self.reasoner = NextorchReasoner(c.vocab_size, c.d_model, c.thought_steps).to(c.device)
        self.sae = IntegratedSAE(c.d_model, c.n_features, c.target_l0).to(c.device)
        self.barrier = FormalBarrier(require_lean=c.require_lean)
        self.replay = CertifiedReplayBuffer(c.replay_capacity, self.barrier)
        self.rng = random.Random(c.seed)
        self.loss_history = []
        self._reset_optimizer()

    def _reset_optimizer(self):
        old = getattr(self, "optimizer", None)
        self.optimizer = MuPScaleCoordinator.optimizer(
            nn.ModuleDict({"reasoner": self.reasoner, "sae": self.sae}),
            self.config.d_model,
            self.config.learning_rate,
        )
        if old is not None:
            for group in self.optimizer.param_groups:
                for param in group["params"]:
                    if param in old.state:
                        self.optimizer.state[param] = copy.deepcopy(old.state[param])

    @property
    def verified_replay_buffer(self):
        return self.replay

    @property
    def parameter_count(self):
        return sum(p.numel() for p in self.reasoner.parameters())

    def generate_problems(self, count):
        if count <= 0:
            raise ValueError("Problem count must be positive")
        problems = []
        for _ in range(count):
            length = self.rng.randint(2, min(4, self.config.vocab_size - 1))
            chain = self.rng.sample(range(self.config.vocab_size), length + 1)
            problems.append(LogicalProblem(tuple(zip(chain, chain[1:])), chain[0]))
        return problems

    def train_replay(self, epochs=1):
        if epochs <= 0:
            raise ValueError("epochs must be positive")
        if not len(self.replay):
            return None
        self.reasoner.train()
        self.sae.train()
        losses = []
        for _ in range(epochs):
            for item in self.replay:
                x = item.problem.encode(self.config.vocab_size, self.config.device)
                target = torch.tensor([item.target], device=self.config.device)
                self.optimizer.zero_grad(set_to_none=True)
                logits, uncertainty, trajectory = self.reasoner(x, capture_trajectory=True)
                reconstruction, features = self.sae(trajectory[-1])
                # This loss is in the reasoner's graph, co-training the latent representation.
                sae_loss = self.sae.compute_loss(trajectory[-1], reconstruction, features)
                loss = (
                    nn.functional.cross_entropy(logits, target)
                    + 0.1 * sae_loss
                    + 0.05 * uncertainty.square().mean()
                )
                if not torch.isfinite(loss):
                    raise FloatingPointError("Nonfinite joint loss")
                loss.backward()
                nn.utils.clip_grad_norm_(
                    list(self.reasoner.parameters()) + list(self.sae.parameters()), 1.0
                )
                self.optimizer.step()
                self.sae.normalize_decoder()
                losses.append(float(loss.detach()))
        mean = sum(losses) / len(losses)
        self.loss_history.append(mean)
        return mean

    def expand_capacity(self, factor=2, max_hidden=2048):
        transform = self.reasoner.thought_cell.candidate_transform
        current = transform[0].out_features
        target = min(max_hidden, int(current * factor))
        if target <= current:
            return False
        self.reasoner.thought_cell.candidate_transform = Net2NetExpansion.widen_sequential(
            transform, 0, target
        )
        self._reset_optimizer()
        return True

    def _plateau(self, patience=3, epsilon=1e-4):
        recent = self.loss_history[-patience:]
        return len(recent) == patience and max(recent) - min(recent) <= epsilon

    def execute_self_improvement_cycle(
        self, n_problems=8, *, problems=None, expert_iteration=True, epochs=1, allow_growth=True
    ):
        started = time.monotonic()
        problems = list(problems) if problems is not None else self.generate_problems(n_problems)
        if not problems:
            raise ValueError("Need at least one logical problem")
        accepted = rejected = expert = model_added = 0
        self.reasoner.eval()
        for problem in problems:
            x = problem.encode(self.config.vocab_size, self.config.device)
            result = self.reasoner.beam_search(x, beam_width=self.config.beam_width)
            predicted = int(result.logits.argmax(-1))
            added, certificate = self.replay.admit(problem, predicted, origin="model")
            model_added += int(added)
            if certificate.valid:
                accepted += 1
            else:
                rejected += 1
            # A separate symbolic expert prevents an empty replay at initialization.
            # Expert proposals are verified by exactly the same formal barrier.
            if expert_iteration:
                reachable = [i for i in problem.reachable() if i != problem.source]
                if reachable:
                    added, _ = self.replay.admit(
                        problem, self.rng.choice(reachable), origin="expert"
                    )
                    expert += int(added)
        loss = self.train_replay(epochs)
        expanded = bool(allow_growth and self._plateau() and self.expand_capacity())
        if expanded:
            self.loss_history.clear()
        elapsed = time.monotonic() - started
        return CycleReport(
            len(problems),
            accepted,
            rejected,
            expert,
            len(self.replay),
            loss,
            self.parameter_count,
            expanded,
            elapsed,
            (model_added + expert) * 60 / max(elapsed, 1e-9),
        )

    def save_checkpoint(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "config": asdict(self.config),
            "hidden": self.reasoner.thought_cell.candidate_transform[0].out_features,
            "reasoner": self.reasoner.state_dict(),
            "sae": self.sae.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "replay": self.replay.to_dict(),
            "loss_history": self.loss_history,
            "rng": self.rng.getstate(),
            "torch_rng": torch.get_rng_state(),
        }
        fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
        os.close(fd)
        try:
            torch.save(payload, temporary)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @classmethod
    def load_checkpoint(cls, path, device="cpu"):
        payload = torch.load(path, map_location=device, weights_only=True)
        if payload.get("version") != 1:
            raise ValueError("Unsupported checkpoint format")
        config = dict(payload["config"], device=device)
        engine = cls(config=NextorchConfig(**config))
        current = engine.reasoner.thought_cell.candidate_transform[0].out_features
        if payload["hidden"] != current:
            engine.expand_capacity(factor=payload["hidden"] / current, max_hidden=payload["hidden"])
        engine.reasoner.load_state_dict(payload["reasoner"])
        engine.sae.load_state_dict(payload["sae"])
        engine.optimizer.load_state_dict(payload["optimizer"])
        engine.replay = CertifiedReplayBuffer.from_dict(payload["replay"], barrier=engine.barrier)
        engine.loss_history = payload["loss_history"]
        engine.rng.setstate(payload["rng"])
        torch.set_rng_state(payload["torch_rng"].cpu())
        return engine
