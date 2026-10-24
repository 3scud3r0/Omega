"""Orange widget: bounded synthesis, diagnostics and optional task training."""

import pyqtgraph as pg
import torch
from Orange.data import Table
from Orange.widgets import gui
from Orange.widgets.settings import Setting
from Orange.widgets.utils.concurrent import ConcurrentWidgetMixin
from Orange.widgets.widget import Input, Msg, Output, OWWidget

from nextorch.core import OrangeBridge
from nextorch.model import NextorchModel


def run_synthesis(data, candidates, width, epochs, state):
    state.set_status("Analyzing manifold and evaluating DAG candidates")
    model = NextorchModel.from_table(data, width=width, candidates=candidates)
    if state.is_interruption_requested():
        return None
    if epochs:
        x, y = model.bridge.transform(data)
        task = "classification" if data.domain.has_discrete_class else "regression"
        state.set_status("Joint model/SAE training")
        model.fit(x, y, epochs=epochs, task=task, cancel=state.is_interruption_requested)
    values = [
        model.signature["intrinsic_dim"],
        model.diagnostics["synflow"],
        model.diagnostics["isometry_ratio"],
        model.diagnostics["parameters"],
        model.trained_steps,
    ]
    diagnostics = OrangeBridge.tensors_to_table(
        torch.tensor([values]),
        ["intrinsic_dim", "synflow", "isometry_ratio", "parameters", "trained_steps"],
    )
    return model, diagnostics


class OWNextorchSynthesizer(OWWidget, ConcurrentWidgetMixin):
    name = "Nextorch Synthesizer"
    description = "Synthesize and train a small DAG from a dataset's spectral signature."
    icon = "icons/synthesizer.svg"
    priority = 10
    candidates = Setting(4)
    width = Setting(32)
    epochs = Setting(20)

    class Inputs:
        data = Input("Data", Table)

    class Outputs:
        model = Output("Nextorch Model", NextorchModel, auto_summary=False)
        diagnostics = Output("Engine Diagnostics", Table)

    class Error(OWWidget.Error):
        failed = Msg("{}")

    def __init__(self):
        super().__init__()
        ConcurrentWidgetMixin.__init__(self)
        self.data = None
        box = gui.vBox(self.controlArea, "Neural synthesis")
        gui.spin(box, self, "candidates", 1, 32, label="Candidates")
        gui.spin(box, self, "width", 8, 256, step=8, label="Latent width")
        gui.spin(box, self, "epochs", 0, 500, label="Training epochs (0 = untrained)")
        gui.button(box, self, "Synthesize", callback=self.apply)
        self.summary = gui.label(box, self, "Connect a data table")
        self.plot = pg.PlotWidget(title="Singular value spectrum")
        self.plot.setLabel("bottom", "Component")
        self.plot.setLabel("left", "Singular value")
        self.mainArea.layout().addWidget(self.plot)

    @Inputs.data
    def set_data(self, data):
        self.cancel()
        self.data = data
        self.Error.failed.clear()
        self.Outputs.model.send(None)
        self.Outputs.diagnostics.send(None)
        self.plot.clear()
        self.summary.setText("Connect a data table" if data is None else f"{len(data)} samples")
        if data is not None:
            self.apply()

    def apply(self):
        self.cancel()
        self.Error.failed.clear()
        self.Outputs.model.send(None)
        self.Outputs.diagnostics.send(None)
        if self.data is not None:
            self.start(run_synthesis, self.data, self.candidates, self.width, self.epochs)

    def on_done(self, result):
        if result is None:
            return
        model, diagnostics = result
        self.summary.setText(
            f"Intrinsic dimension: {model.signature['intrinsic_dim']}\n"
            f"SynFlow: {model.diagnostics['synflow']:.3g}\n"
            f"Isometry proxy: {model.diagnostics['isometry_ratio']:.3g}\n"
            f"Training steps: {model.trained_steps}"
        )
        self.plot.clear()
        self.plot.plot(model.signature["singular_values"].numpy(), pen="#3bbfba", symbol="o")
        self.Outputs.model.send(model)
        self.Outputs.diagnostics.send(diagnostics)

    def on_exception(self, exc):
        self.Error.failed(str(exc))

    def onDeleteWidget(self):
        self.shutdown()
        super().onDeleteWidget()
