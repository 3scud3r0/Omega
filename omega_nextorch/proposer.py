"""Bounded Nextorch proposals, explicitly separate from exact admission."""
from __future__ import annotations

from dataclasses import dataclass

from omega_open import logic
from .gate import validate_domain


@dataclass(frozen=True)
class NeuralBudget:
    epochs: int = 80
    width: int = 16
    candidates: int = 4
    policy_steps: int = 3
    seed: int = 42

    def __post_init__(self):
        for name, upper in (("epochs", 1000), ("width", 128), ("candidates", 32),
                            ("policy_steps", 100)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= upper:
                raise ValueError(f"{name} deve estar entre 1 e {upper}")
        if type(self.seed) is not int or not 0 <= self.seed < 2**32:
            raise ValueError("Seed inválida")


def propose(task, budget):
    validate_domain(task)
    try:
        import torch
        from nextorch import NextorchModel, seed_everything
    except ImportError as exc:
        raise RuntimeError("Instale o extra neural: pip install -e '.[neural]'") from exc
    seed_everything(budget.seed)
    n = task["arity"]
    # A constant input supports the valid zero-arity Boolean domain.
    x = torch.tensor([[(row >> j) & 1 for j in range(max(n, 1))]
                      for row in range(len(task["outputs"]))], dtype=torch.float32)
    y = torch.tensor(task["outputs"], dtype=torch.long)
    model = NextorchModel.from_tensor(x, width=budget.width, candidates=budget.candidates,
                                     policy_steps=budget.policy_steps)
    history = model.fit(x, y, epochs=budget.epochs, lr=0.03)
    with torch.no_grad():
        logits = model(x)
        if not torch.isfinite(logits).all():
            raise ValueError("Nextorch produziu valores não finitos")
        predicted = logits.argmax(-1).tolist()
        trajectory = model.trajectory(x)
        _, features = model.sae(trajectory[-1])
        active = float((features != 0).float().sum(-1).mean())
    # Saliency selects variable order. It cannot establish circuit correctness.
    probe = x.clone().requires_grad_(True)
    scores = model(probe)
    gradients = torch.autograd.grad((scores[:, 1] - scores[:, 0]).sum(), probe)[0]
    importance = gradients.abs().mean(0).tolist()
    order = sorted(range(n), key=lambda j: (-importance[j], j))
    return [
        ("nextorch:predicted-table", logic.encode(logic.anf(predicted, n))),
        ("nextorch:saliency+exact-shannon",
         logic.encode(logic.shannon(task["outputs"], n, order))),
    ], {
        "training_rows": len(y), "evaluation": "exhaustive specification, not held-out generalization",
        "epochs": len(history), "first_loss": history[0], "last_loss": history[-1],
        "prediction_matches": sum(a == b for a, b in zip(predicted, task["outputs"])),
        "variable_order": order, "mean_active_sae_features": active,
        "latent_steps": model.thought_steps,
        "architecture": model.graph.architecture.to_dict(),
    }
