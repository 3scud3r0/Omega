"""Render actual Orange widgets in a headless environment after iris_workflow.py."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/nextorch-matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/nextorch-cache")
os.environ.setdefault("XDG_CONFIG_HOME", "/tmp/nextorch-config")
import torch
from AnyQt.QtWidgets import QApplication
from Orange.data import Table

from nextorch import NextorchModel
from nextorch.core import OrangeBridge
from nextorch.orange.OWFormalLoopMonitor import OWFormalLoopMonitor, replay_to_table
from nextorch.orange.OWLatentInspector import OWLatentInspector, inspect_model
from nextorch.orange.OWNextorchSynthesizer import OWNextorchSynthesizer


class State:
    def set_status(self, value):
        pass

    def is_interruption_requested(self):
        return False


def main():
    torch.set_num_threads(2)
    app = QApplication.instance() or QApplication([])
    directory = Path("artifacts/gallery")
    directory.mkdir(parents=True, exist_ok=True)
    model = NextorchModel.load("artifacts/iris/iris_model.pt")
    table = Table("iris")
    synth = OWNextorchSynthesizer()
    synth.data = table
    values = [
        model.signature["intrinsic_dim"],
        model.diagnostics["synflow"],
        model.diagnostics["isometry_ratio"],
    ]
    diagnostics = OrangeBridge.tensors_to_table(
        torch.tensor([values]), ["dimension", "synflow", "isometry"]
    )
    synth.on_done((model, diagnostics))
    inspector = OWLatentInspector()
    inspector.model = model
    inspector.data = table
    inspector.dimension_index = 1
    inspector.on_done(inspect_model(model, table, "PCA", 3, State()))
    monitor = OWFormalLoopMonitor()
    engine = model.make_formal_engine()
    for _ in range(3):
        report = engine.execute_self_improvement_cycle(n_problems=8)
        monitor.on_partial_result((engine, report, replay_to_table(engine)))
    for name, widget in [("synthesizer", synth), ("inspector", inspector), ("formal", monitor)]:
        widget.resize(1050, 700)
        widget.show()
        app.processEvents()
        assert widget.grab().save(str(directory / f"{name}.png"))
        widget.onDeleteWidget()
        widget.close()
    print(f"Saved three real widget screenshots to {directory}")


if __name__ == "__main__":
    main()
