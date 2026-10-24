"""Held-out Iris experiment, Orange feature export and portable model persistence.

Run: .venv/bin/python examples/iris_workflow.py --output artifacts/iris
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from Orange.data import Table
from sklearn.model_selection import train_test_split

from nextorch import NextorchModel, seed_everything
from nextorch.core import OrangeBridge
from nextorch.evolution.replay_buffer import atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/iris"))
    args = parser.parse_args()
    torch.set_num_threads(2)
    seed_everything(42)
    table = Table("iris")
    train_indices, test_indices = train_test_split(
        np.arange(len(table)), test_size=0.3, stratify=table.Y, random_state=42
    )
    train, test = table[train_indices], table[test_indices]
    # Only the training partition fits imputation, normalization and architecture selection.
    model = NextorchModel.from_table(train, width=32, candidates=6)
    x_train, y_train = model.bridge.transform(train)
    x_test, y_test = model.bridge.transform(test)
    history = model.fit(x_train, y_train, epochs=200, lr=0.02)
    with torch.no_grad():
        predictions = model(x_test).argmax(-1)
        accuracy = float((predictions == y_test).float().mean())
        latent = model.trajectory(x_test)[-1]
        features = model.sae(latent)[1]
    args.output.mkdir(parents=True, exist_ok=True)
    enriched = OrangeBridge.append_features(test, features)
    enriched.save(str(args.output / "iris_features.tab"))
    model.save(args.output / "iris_model.pt")
    restored = NextorchModel.load(args.output / "iris_model.pt")
    torch.testing.assert_close(restored(x_test), model(x_test))
    result = {
        "seed": 42,
        "train_samples": len(train),
        "test_samples": len(test),
        "held_out_accuracy": accuracy,
        "initial_joint_loss": history[0],
        "final_joint_loss": history[-1],
        "intrinsic_dim": model.signature["intrinsic_dim"],
        "sparse_features": features.shape[1],
        "trained_steps": model.trained_steps,
    }
    atomic_json(args.output / "report.json", result)
    print(json.dumps(result, indent=2))
    if accuracy < 0.8:
        raise SystemExit("Held-out Iris smoke test failed: accuracy below 0.8")


if __name__ == "__main__":
    main()
