import importlib.metadata

import numpy as np
import pytest

pytest.importorskip("Orange")
from Orange.data import Table
from Orange.widgets.tests import base as widget_test_base

from nextorch.model import NextorchModel
from nextorch.orange.OWFormalLoopMonitor import OWFormalLoopMonitor, read_domain_rules
from nextorch.orange.OWLatentInspector import OWLatentInspector
from nextorch.orange.OWNextorchSynthesizer import OWNextorchSynthesizer

pytestmark = pytest.mark.orange


class TestNextorchWidgets(widget_test_base.WidgetTest):
    def setUp(self):
        super().setUp()
        self.widget = self.create_widget(
            OWNextorchSynthesizer, stored_settings={"epochs": 0, "candidates": 1, "width": 8}
        )

    def test_registered_category_and_complete_canvas_flow(self):
        points = importlib.metadata.entry_points(group="orange.widgets")
        assert any(
            p.name == "Nextorch Epistemic AI" and p.value == "nextorch.orange" for p in points
        )
        data = Table("iris")[:24]
        synthesizer = self.create_widget(
            OWNextorchSynthesizer, stored_settings={"epochs": 3, "candidates": 2, "width": 16}
        )
        self.send_signal(synthesizer.Inputs.data, data, widget=synthesizer)
        self.wait_until_finished(synthesizer, timeout=30000)
        assert not synthesizer.Error.failed.is_shown(), synthesizer.Error.failed.formatted
        model = self.get_output(synthesizer.Outputs.model, widget=synthesizer)
        assert isinstance(model, NextorchModel) and model.trained_steps == 3
        assert len(self.get_output(synthesizer.Outputs.diagnostics, widget=synthesizer)) == 1

        inspector = self.create_widget(OWLatentInspector)
        self.send_signal(inspector.Inputs.model, model, widget=inspector)
        self.send_signal(inspector.Inputs.data, data, widget=inspector)
        self.wait_until_finished(inspector, timeout=30000)
        assert not inspector.Error.failed.is_shown(), inspector.Error.failed.formatted
        features = self.get_output(inspector.Outputs.features, widget=inspector)
        assert len(features) == len(data)
        assert len(features.domain.attributes) == len(data.domain.attributes) + model.sae.n_features
        np.testing.assert_array_equal(features.Y, data.Y)
        inspector.dimension_index = 1
        inspector.apply()
        self.wait_until_finished(inspector, timeout=30000)
        assert inspector.figure.axes[0].name == "3d"

        monitor = self.create_widget(
            OWFormalLoopMonitor, stored_settings={"cycles": 1, "problems_per_cycle": 2}
        )
        self.send_signal(monitor.Inputs.model, model, widget=monitor)
        self.send_signal(
            monitor.Inputs.rules, '{"premises": [[0, 1], [1, 2]], "source": 0}', widget=monitor
        )
        monitor.run()
        self.wait_until_finished(monitor, timeout=30000)
        assert not monitor.Error.failed.is_shown(), monitor.Error.failed.formatted
        certified = self.get_output(monitor.Outputs.certified, widget=monitor)
        assert len(certified) >= 1 and certified.domain.class_var.name == "Conclusion"
        assert all(len(str(row["Certificate SHA256"])) == 64 for row in certified)
        assert len(monitor.reports) == 1
        monitor.stop()

        self.send_signal(inspector.Inputs.model, None, widget=inspector)
        assert self.get_output(inspector.Outputs.features, widget=inspector) is None
        self.send_signal(synthesizer.Inputs.data, None, widget=synthesizer)
        assert self.get_output(synthesizer.Outputs.model, widget=synthesizer) is None
        self.send_signal(monitor.Inputs.model, None, widget=monitor)
        assert self.get_output(monitor.Outputs.certified, widget=monitor) is None

    def test_error_recovery_and_input_replacement(self):
        widget = self.create_widget(
            OWNextorchSynthesizer, stored_settings={"epochs": 0, "candidates": 1, "width": 8}
        )
        data = Table("iris")[:20]
        self.send_signal(widget.Inputs.data, data[:0], widget=widget)
        self.wait_until_finished(widget, timeout=30000)
        assert widget.Error.failed.is_shown()
        self.send_signal(widget.Inputs.data, data, widget=widget)
        self.wait_until_finished(widget, timeout=30000)
        assert not widget.Error.failed.is_shown()
        assert self.get_output(widget.Outputs.model, widget=widget) is not None
        # Replacement while a task is running must invalidate stale output.
        self.send_signal(widget.Inputs.data, data, widget=widget, wait=-1)
        self.send_signal(widget.Inputs.data, None, widget=widget)
        self.wait_until_finished(widget, timeout=30000)
        assert self.get_output(widget.Outputs.model, widget=widget) is None

    def test_invalid_rules_are_displayed_without_producing_dataset(self):
        data = Table("iris")[:10]
        model = NextorchModel.from_table(data, width=8, candidates=1)
        monitor = self.create_widget(OWFormalLoopMonitor)
        self.send_signal(monitor.Inputs.model, model, widget=monitor)
        self.send_signal(
            monitor.Inputs.rules, '{"premises": [[0, -2]], "source": 0}', widget=monitor
        )
        monitor.run()
        assert monitor.Error.failed.is_shown()
        assert self.get_output(monitor.Outputs.certified, widget=monitor) is None


def test_domain_rules_smt2_and_json():
    parsed = read_domain_rules(
        "(declare-const P_0 Bool) (declare-const P_1 Bool) (assert P_0) (assert (=> P_0 P_1))"
    )
    assert parsed.reachable() == [0, 1]
    assert read_domain_rules('{"premises": [[4, 5]], "source": 4}').reachable() == [4, 5]
    with pytest.raises(ValueError):
        read_domain_rules("(declare-const P_0 Bool) (assert (not P_0))")


@pytest.mark.parametrize("method", ["t-SNE", "UMAP"])
def test_projection_backends_execute_and_return_finite_coordinates(method):
    if method == "UMAP":
        pytest.importorskip("umap")
    from nextorch.orange.OWLatentInspector import inspect_model

    class State:
        def set_status(self, value):
            pass

        def is_interruption_requested(self):
            return False

    data = Table("iris")[:12]
    model = NextorchModel.from_table(data, width=8, candidates=1)
    table, coordinates, _ = inspect_model(model, data, method, 2, State())
    assert coordinates.shape == (5, 12, 2) and np.isfinite(coordinates).all()
    assert len(table) == len(data)


def test_workflow_widget_descriptions_and_links_are_loadable():
    from pathlib import Path

    from orangecanvas.registry import WidgetRegistry
    from orangecanvas.scheme import Scheme
    from orangewidget.workflow.discovery import WidgetDiscovery

    registry = WidgetRegistry()
    discovery = WidgetDiscovery(registry)
    for package in ["nextorch.orange", "Orange.widgets.data"]:
        discovery.process_category_package(package)
    names = {w.qualified_name for w in registry.widgets()}
    assert "nextorch.orange.OWNextorchSynthesizer.OWNextorchSynthesizer" in names
    assert "nextorch.orange.OWFormalLoopMonitor.OWFormalLoopMonitor" in names
    scheme = Scheme()
    with (Path(__file__).parents[2] / "exemplos/nextorch/nextorch.ows").open("rb") as stream:
        scheme.load_from(stream, registry=registry)
    assert len(scheme.nodes) == 6 and len(scheme.links) == 6
