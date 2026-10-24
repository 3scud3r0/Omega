"""Finite-domain synthesis with explicit proof gating and no stale outputs."""
import tempfile
from pathlib import Path

from Orange.data import Table
from Orange.widgets import gui
from Orange.widgets.settings import Setting
from Orange.widgets.utils.concurrent import ConcurrentWidgetMixin
from Orange.widgets.widget import Input, Msg, Output, OWWidget

from omega_nextorch.gate import load_verified
from omega_nextorch.orange_bridge import task_from_table
from omega_nextorch.pipeline import synthesize
from omega_nextorch.proposer import NeuralBudget


def certify_table(data, epochs, require_lean, state):
    task = task_from_table(data)
    state.set_status("Nextorch propõe; Ômega verifica todas as entradas")
    with tempfile.TemporaryDirectory(prefix="omega-orange-") as tmp:
        target = Path(tmp) / "result"
        manifest = synthesize([task], target, NeuralBudget(epochs=epochs), require_lean)
        if state.is_interruption_requested():
            return None
        return load_verified(target / "task_000.json"), manifest["tasks"][0]


class OWOmegaCertifier(OWWidget, ConcurrentWidgetMixin):
    name = "Omega Certifier"
    description = "Certifica a síntese neural em uma tabela-verdade booleana completa."
    icon = "omega.svg"
    priority = 10
    want_main_area = False
    epochs = Setting(20)
    require_lean = Setting(True)

    class Inputs:
        data = Input("Truth Table", Table)

    class Outputs:
        certificate = Output("Certified Circuit", dict, auto_summary=False)
        report = Output("Admission Report", dict, auto_summary=False)

    class Error(OWWidget.Error):
        failed = Msg("{}")

    def __init__(self):
        super().__init__()
        ConcurrentWidgetMixin.__init__(self)
        self.data = None
        box = gui.vBox(self.controlArea, "Ômega + Nextorch")
        gui.spin(box, self, "epochs", 1, 1000, label="Épocas")
        gui.checkBox(box, self, "require_lean", "Exigir prova Lean 4")
        gui.button(box, self, "Sintetizar e certificar", callback=self.apply)
        self.summary = gui.label(box, self, "Conecte uma tabela-verdade completa (0/1).")

    @Inputs.data
    def set_data(self, data):
        self.cancel()
        self.data = data
        self.Error.failed.clear()
        self.Outputs.certificate.send(None)
        self.Outputs.report.send(None)
        self.summary.setText("Conecte uma tabela-verdade completa (0/1)." if data is None
                             else f"{len(data)} linhas; clique para certificar.")

    def apply(self):
        self.cancel()
        self.Error.failed.clear()
        self.Outputs.certificate.send(None)
        self.Outputs.report.send(None)
        if self.data is not None:
            self.start(certify_table, self.data, self.epochs, self.require_lean)

    def on_done(self, result):
        if result is not None:
            certificate, report = result
            self.Outputs.certificate.send(certificate)
            self.Outputs.report.send(report)
            self.summary.setText(f"Certificado: {certificate['checked_rows']} linhas verificadas.")

    def on_exception(self, error):
        self.Error.failed(str(error))

    def onDeleteWidget(self):
        self.shutdown()
        super().onDeleteWidget()
