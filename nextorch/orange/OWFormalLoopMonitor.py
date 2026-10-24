"""Orange widget: cancellable expert iteration and certified dataset export."""

import copy
import json
from pathlib import Path

import numpy as np
import pyqtgraph as pg
import z3
from Orange.data import ContinuousVariable, DiscreteVariable, Domain, StringVariable, Table
from Orange.widgets import gui
from Orange.widgets.settings import Setting
from Orange.widgets.utils.concurrent import ConcurrentWidgetMixin
from Orange.widgets.widget import Input, Msg, Output, OWWidget

from nextorch.formal import LogicalProblem
from nextorch.model import NextorchModel


def read_domain_rules(text):
    """Accept JSON {premises, source}, or SMT2 implication rules over P_<index>."""
    if len(text) > 65536:
        raise ValueError("Domain rules exceed 64 KiB")
    if text.lstrip().startswith("{"):
        item = json.loads(text)
        return LogicalProblem(tuple(tuple(e) for e in item["premises"]), item["source"])
    expressions = z3.parse_smt2_string(text, ctx=z3.Context())
    edges, sources = [], []
    for expression in expressions:

        def index(value):
            if not z3.is_const(value) or value.sort().kind() != z3.Z3_BOOL_SORT:
                raise ValueError("Rules require Boolean proposition constants P_<index>")
            name = str(value)
            if not name.startswith("P_") or not name[2:].isdigit():
                raise ValueError("Use proposition names P_<nonnegative integer>")
            return int(name[2:])

        if z3.is_implies(expression):
            edges.append((index(expression.arg(0)), index(expression.arg(1))))
        else:
            sources.append(index(expression))
    if len(sources) != 1:
        raise ValueError("SMT2 requires exactly one asserted source and implication rules")
    return LogicalProblem(tuple(edges), sources[0])


def replay_to_table(engine):
    items = list(engine.replay)
    length = max((1 + 2 * len(i.problem.premises) for i in items), default=1)
    x = np.full((len(items), length), np.nan)
    y = np.empty(len(items))
    metas = np.empty((len(items), 3), dtype=object)
    for row, item in enumerate(items):
        tokens = [item.problem.source] + [p for edge in item.problem.premises for p in edge]
        x[row, : len(tokens)] = tokens
        y[row] = item.target
        metas[row] = [item.certificate.digest, item.certificate.proof, item.origin]
    domain = Domain(
        [ContinuousVariable(f"token_{i}") for i in range(length)],
        DiscreteVariable("Conclusion", values=[f"P_{i}" for i in range(engine.config.vocab_size)]),
        [
            StringVariable("Certificate SHA256"),
            StringVariable("Z3 proof"),
            StringVariable("Origin"),
        ],
    )
    return Table.from_numpy(domain, x, y, metas)


def run_formal(engine, cycles, problems_per_cycle, rules, state):
    engine = copy.deepcopy(engine)
    reports = []
    for _ in range(cycles):
        if state.is_interruption_requested():
            break
        state.set_status("Propose → verify → admit → train")
        report = engine.execute_self_improvement_cycle(
            problems=[rules] if rules is not None else None, n_problems=problems_per_cycle
        )
        reports.append(report)
        state.set_partial_result((copy.deepcopy(engine), report, replay_to_table(engine)))
        state.set_progress_value(100 * len(reports) / cycles)
    return engine, reports


class OWFormalLoopMonitor(OWWidget, ConcurrentWidgetMixin):
    name = "Formal Loop Monitor"
    description = "Run proof-gated expert iteration; inspect approval rates and network capacity."
    icon = "icons/formal.svg"
    priority = 30
    cycles = Setting(3)
    problems_per_cycle = Setting(8)
    rules_path = Setting("")

    class Inputs:
        model = Input("Nextorch Model", NextorchModel, auto_summary=False)
        rules = Input("Domain Rules", str, auto_summary=False)

    class Outputs:
        certified = Output("Certified Dataset", Table)

    class Error(OWWidget.Error):
        failed = Msg("{}")

    def __init__(self):
        super().__init__()
        ConcurrentWidgetMixin.__init__(self)
        self.engine = self.model = self.rules = None
        self.reports = []
        box = gui.vBox(self.controlArea, "Certified expert iteration")
        gui.spin(box, self, "cycles", 1, 100, label="Cycles")
        gui.spin(box, self, "problems_per_cycle", 1, 32, label="Problems per cycle")
        gui.lineEdit(box, self, "rules_path", label="Rules file (.json/.smt2)")
        gui.button(box, self, "Start / continue", callback=self.run)
        gui.button(box, self, "Stop after current cycle", callback=self.stop)
        self.summary = gui.label(box, self, "Connect a synthesized model")
        self.loss_plot = pg.PlotWidget(title="Certified replay training loss")
        self.capacity_plot = pg.PlotWidget(title="Reasoner parameter count")
        self.mainArea.layout().addWidget(self.loss_plot)
        self.mainArea.layout().addWidget(self.capacity_plot)

    @Inputs.model
    def set_model(self, model):
        self.cancel()
        self.model, self.engine = model, None
        self.reports = []
        self.loss_plot.clear()
        self.capacity_plot.clear()
        self.Outputs.certified.send(None)
        self.summary.setText(
            "Ready to start" if model is not None else "Connect a synthesized model"
        )

    @Inputs.rules
    def set_rules(self, rules):
        self.cancel()
        self.rules = rules
        self.engine = None
        self.reports = []
        self.Outputs.certified.send(None)

    def run(self):
        self.cancel()
        self.Error.failed.clear()
        if self.model is None:
            return
        try:
            text = self.rules
            if text is None and self.rules_path:
                path = Path(self.rules_path)
                if path.stat().st_size > 65536:
                    raise ValueError("Rules file exceeds 64 KiB")
                text = path.read_text(encoding="utf-8")
            rules = read_domain_rules(text) if text else None
            if self.engine is None:
                largest = (
                    max([rules.source] + [i for e in rules.premises for i in e]) if rules else 15
                )
                if largest > 4095:
                    raise ValueError("Widget vocabulary is limited to 4096 propositions")
                self.engine = self.model.make_formal_engine(vocab_size=max(16, largest + 1))
            self.start(run_formal, self.engine, self.cycles, self.problems_per_cycle, rules)
        except (OSError, ValueError, z3.Z3Exception) as exc:
            self.Error.failed(str(exc))

    def stop(self):
        # Cancellation is observed between cycles. The latest complete partial result is retained.
        self.cancel()
        self.summary.setText(self.summary.text() + "\nStopped; completed cycles retained.")

    def on_partial_result(self, result):
        self.engine, report, table = result
        self.reports.append(report)
        total = report.model_accepted + report.model_rejected
        self.summary.setText(
            f"Certified replay: {report.replay_size}\n"
            f"Model approval: {report.model_accepted}/{total}\n"
            f"Expert examples added: {report.expert_added}\n"
            f"Certificates/min: {report.certified_per_minute:.1f}"
        )
        self.loss_plot.clear()
        self.loss_plot.plot([r.loss or 0 for r in self.reports], pen="#3bbfba")
        self.capacity_plot.clear()
        self.capacity_plot.plot([r.parameters for r in self.reports], pen="#efaa54")
        self.Outputs.certified.send(table)

    def on_done(self, result):
        self.engine = result[0]

    def on_exception(self, exc):
        self.Error.failed(str(exc))

    def onDeleteWidget(self):
        self.shutdown()
        super().onDeleteWidget()
