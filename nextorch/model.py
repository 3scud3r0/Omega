"""Public tabular model joining DAG synthesis, latent recurrence and an integrated SAE."""

import copy
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

import torch
from torch import nn

from .config import NextorchConfig
from .core import ManifoldAnalyzer, OrangeBridge
from .core.orange_bridge import ColumnState
from .engine import LatentThoughtBlock
from .evolution import NextorchEngine
from .interpretability import IntegratedSAE
from .synthesis import Architecture, GFlowNetSynthesizer
from .verifier import MuPScaleCoordinator


class NextorchModel(nn.Module):
    def __init__(self, graph, signature, diagnostics, bridge=None, thought_steps=4):
        super().__init__()
        self.graph = graph
        self.signature, self.diagnostics, self.bridge = signature, diagnostics, bridge
        width = graph.architecture.width
        self.thought_steps = thought_steps
        self.thought_cell = LatentThoughtBlock(width)
        self.sae = IntegratedSAE(width, width * 4, min(8, width * 4))
        self.trained_steps = 0
        MuPScaleCoordinator.apply_mup_coordinates(self.thought_cell, width)

    def trajectory(self, x):
        context = self.graph.encode(x)
        states, h = [context], context
        for _ in range(self.thought_steps):
            h = self.thought_cell(h, context)
            states.append(h)
        return torch.stack(states)

    def forward(self, x):
        return self.graph.policy_head(self.trajectory(x)[-1])

    def fit(self, x, y=None, epochs=20, task="classification", lr=1e-3, cancel=None):
        if epochs <= 0 or task not in ("classification", "regression"):
            raise ValueError("Positive epochs and classification/regression task required")
        self.train()
        optimizer = MuPScaleCoordinator.optimizer(self, self.graph.architecture.width, lr)
        history = []
        for _ in range(epochs):
            if cancel is not None and cancel():
                break
            optimizer.zero_grad(set_to_none=True)
            latent = self.trajectory(x)[-1]
            reconstructed, features = self.sae(latent)
            loss = 0.1 * self.sae.compute_loss(latent, reconstructed, features)
            if y is not None:
                logits = self.graph.policy_head(latent)
                if task == "classification":
                    valid = torch.isfinite(y.float())
                    if y.ndim != 1:
                        raise ValueError("Classification currently supports a single target")
                    if valid.any():
                        loss = loss + nn.functional.cross_entropy(logits[valid], y[valid].long())
                else:
                    targets = y.reshape_as(logits)
                    valid = torch.isfinite(targets)
                    if valid.any():
                        loss = loss + nn.functional.mse_loss(logits[valid], targets[valid])
            if not torch.isfinite(loss):
                raise FloatingPointError("Nonfinite tabular training loss")
            loss.backward()
            nn.utils.clip_grad_norm_(self.parameters(), 1.0)
            optimizer.step()
            self.sae.normalize_decoder()
            history.append(float(loss.detach()))
            self.trained_steps += 1
        self.eval()
        return history

    def make_formal_engine(self, vocab_size=16):
        width = self.graph.architecture.width
        config = NextorchConfig(
            vocab_size=vocab_size,
            d_model=width,
            n_features=self.sae.n_features,
            target_l0=self.sae.target_l0,
            thought_steps=self.thought_steps,
        )
        engine = NextorchEngine(config=config)
        engine.reasoner.thought_cell = copy.deepcopy(self.thought_cell)
        engine.sae = copy.deepcopy(self.sae)
        engine._reset_optimizer()
        return engine

    @classmethod
    def from_tensor(
        cls, x, output_dim=2, width=32, candidates=4, labels=None, bridge=None, policy_steps=3
    ):
        signature = ManifoldAnalyzer.compute_spectral_signature(x, labels=labels)
        synthesizer = GFlowNetSynthesizer(width=width)
        optimizer = torch.optim.Adam(synthesizer.parameters(), lr=0.01)
        for _ in range(policy_steps):
            synthesizer.train_step(signature, output_dim, optimizer, batch_size=2)
        result = synthesizer.synthesize(signature, output_dim, candidates)
        return cls(result.model, signature, result.diagnostics, bridge)

    def save(self, path):
        """Save tensor weights and plain metadata; never pickle a live Python model."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        bridge = (
            None
            if self.bridge is None
            else {
                "columns": [asdict(column) for column in self.bridge.columns],
                "feature_names": self.bridge.feature_names,
            }
        )
        payload = {
            "version": 1,
            "architecture": self.graph.architecture.to_dict(),
            "signature": self.signature,
            "diagnostics": self.diagnostics,
            "bridge": bridge,
            "thought_steps": self.thought_steps,
            "trained_steps": self.trained_steps,
            "weights": self.state_dict(),
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
    def load(cls, path, device="cpu"):
        payload = torch.load(path, map_location=device, weights_only=True)
        if payload.get("version") != 1:
            raise ValueError("Unsupported tabular model checkpoint")
        bridge = None
        if payload["bridge"] is not None:
            bridge = OrangeBridge()
            bridge.columns = [ColumnState(**column) for column in payload["bridge"]["columns"]]
            bridge.feature_names = payload["bridge"]["feature_names"]
        graph = Architecture.from_dict(payload["architecture"]).build()
        model = cls(
            graph, payload["signature"], payload["diagnostics"], bridge, payload["thought_steps"]
        )
        model.load_state_dict(payload["weights"])
        model.trained_steps = payload["trained_steps"]
        return model.to(device).eval()

    @classmethod
    def from_table(cls, table, width=32, candidates=4):
        bridge = OrangeBridge()
        x, y = bridge.fit_transform(table)
        classes = table.domain.class_vars
        if len(classes) > 1:
            raise ValueError("Synthesis widget supports a single target")
        output_dim = len(classes[0].values) if classes and classes[0].is_discrete else 1
        labels = (
            y
            if classes and classes[0].is_discrete and y is not None and torch.isfinite(y).all()
            else None
        )
        return cls.from_tensor(x, max(1, output_dim), width, candidates, labels, bridge)
