"""Orange widget: 2D/3D trajectory projection and metadata-preserving SAE export."""

import copy

import numpy as np
import torch
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from Orange.data import Table
from Orange.widgets import gui
from Orange.widgets.settings import Setting
from Orange.widgets.utils.concurrent import ConcurrentWidgetMixin
from Orange.widgets.widget import Input, Msg, Output, OWWidget

from nextorch.core import OrangeBridge
from nextorch.interpretability import FeatureVocabulary
from nextorch.model import NextorchModel


def inspect_model(model, data, method, dimensions, state):
    model = copy.deepcopy(model).eval()
    if model.bridge is None:
        raise ValueError("Model has no fitted Orange preprocessing bridge")
    x, _ = model.bridge.transform(data)
    x = x.to(next(model.parameters()).device)
    with torch.no_grad():
        # Full feature output, bounded projection for responsive visualization.
        features = []
        for batch in x.split(256):
            if state.is_interruption_requested():
                return None
            features.append(model.sae(model.trajectory(batch)[-1])[1])
        features = torch.cat(features)
        trajectory = model.trajectory(x[:64]).cpu()
    flat = trajectory.flatten(0, 1).numpy()
    state.set_status(f"Projecting {len(flat)} latent states using {method}")
    if method == "PCA":
        centered = flat - flat.mean(0)
        u, s, _ = np.linalg.svd(centered, full_matrices=False)
        coordinates = u[:, :dimensions] * s[:dimensions]
        coordinates = np.pad(coordinates, ((0, 0), (0, max(0, dimensions - coordinates.shape[1]))))
    elif method == "t-SNE":
        from sklearn.manifold import TSNE

        coordinates = TSNE(
            n_components=dimensions,
            perplexity=min(30, max(1, len(flat) // 4)),
            random_state=42,
            init="random",
        ).fit_transform(flat)
    elif method == "UMAP":
        try:
            from umap import UMAP
        except ImportError as exc:
            raise RuntimeError("Install nextorch-ai[umap] to enable UMAP projection") from exc
        coordinates = UMAP(
            n_components=dimensions,
            n_neighbors=min(15, len(flat) - 1),
            random_state=42,
            init="random",
        ).fit_transform(flat)
    else:
        raise ValueError("Unknown projection method")
    table = OrangeBridge.append_features(data, features)
    labels = FeatureVocabulary().decode(features.mean(0), top_k=6)[0]
    return table, coordinates.reshape(*trajectory.shape[:2], dimensions), labels


class OWLatentInspector(OWWidget, ConcurrentWidgetMixin):
    name = "Latent Inspector"
    description = "Inspect latent trajectories and export sparse activations as derived features."
    icon = "icons/inspector.svg"
    priority = 20
    method_index = Setting(0)
    dimension_index = Setting(0)

    class Inputs:
        model = Input("Nextorch Model", NextorchModel, auto_summary=False)
        data = Input("Data", Table)

    class Outputs:
        features = Output("Decoded Features Table", Table)

    class Error(OWWidget.Error):
        failed = Msg("{}")

    def __init__(self):
        super().__init__()
        ConcurrentWidgetMixin.__init__(self)
        self.model = self.data = None
        box = gui.vBox(self.controlArea, "Latent audit")
        gui.comboBox(box, self, "method_index", items=["PCA", "t-SNE", "UMAP"], callback=self.apply)
        gui.comboBox(box, self, "dimension_index", items=["2D", "3D"], callback=self.apply)
        self.summary = gui.label(box, self, "Connect a model and data")
        self.figure = Figure(figsize=(6, 5), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.mainArea.layout().addWidget(self.canvas)

    @Inputs.model
    def set_model(self, model):
        self.cancel()
        self.model = model

    @Inputs.data
    def set_data(self, data):
        self.cancel()
        self.data = data

    def handleNewSignals(self):
        self.apply()

    def apply(self):
        self.cancel()
        self.Error.failed.clear()
        self.Outputs.features.send(None)
        self.figure.clear()
        self.canvas.draw_idle()
        if self.model is not None and self.data is not None:
            if len(self.data) == 0:
                self.Error.failed("Need a nonempty table")
                return
            self.start(
                inspect_model,
                self.model,
                self.data,
                ["PCA", "t-SNE", "UMAP"][self.method_index],
                self.dimension_index + 2,
            )
        else:
            self.summary.setText("Connect a model and data")

    def on_done(self, result):
        if result is None:
            return
        table, coordinates, labels = result
        self.figure.clear()
        axes = self.figure.add_subplot(111, projection="3d" if coordinates.shape[-1] == 3 else None)
        for sample in range(min(coordinates.shape[1], 16)):
            path = coordinates[:, sample]
            axes.plot(*path.T, marker="o", alpha=0.65)
        axes.set_title("Latent trajectories: input → final thought (first 16 samples)")
        self.canvas.draw_idle()
        self.summary.setText(
            "Active features (user annotations required):\n"
            + "\n".join(f"{v['label']}: {v['activation']:.3f}" for v in labels)
            + f"\nModel training steps: {self.model.trained_steps}"
        )
        self.Outputs.features.send(table)

    def on_exception(self, exc):
        self.Error.failed(str(exc))

    def onDeleteWidget(self):
        self.shutdown()
        super().onDeleteWidget()
