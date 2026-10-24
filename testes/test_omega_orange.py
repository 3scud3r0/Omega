import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "omega-matplotlib"))
os.environ.setdefault("XDG_CONFIG_HOME", os.path.join(tempfile.gettempdir(), "omega-config"))
os.environ.setdefault("XDG_CACHE_HOME", os.path.join(tempfile.gettempdir(), "omega-cache"))

try:
    import pytest
    import numpy as np
    import Orange
except ImportError:
    import unittest
    raise unittest.SkipTest("Install the dev and orange extras")
from Orange.data import ContinuousVariable, DiscreteVariable, Domain, Table
from Orange.widgets.tests import base as widget_test_base
from omega_nextorch.orange_bridge import task_from_table
from omega_nextorch.orange.OWOmegaCertifier import OWOmegaCertifier
from omega_nextorch.gate import verify


def truth_table():
    domain = Domain([ContinuousVariable("x0"), ContinuousVariable("x1")],
                    DiscreteVariable("xor", values=("0", "1")))
    return Table.from_numpy(domain, np.array([[0, 0], [1, 0], [0, 1], [1, 1]]),
                            np.array([0, 1, 1, 0]))


def test_boolean_bridge_rejects_partial_duplicate_and_missing_data():
    data = truth_table()
    assert task_from_table(data)["outputs"] == [0, 1, 1, 0]
    for invalid in (data[:3], data[[0, 0, 2, 3]]):
        with pytest.raises(ValueError):
            task_from_table(invalid)
    with data.unlocked():
        data.X[0, 0] = np.nan
    with pytest.raises(ValueError):
        task_from_table(data)


def test_boolean_bridge_respects_categorical_labels():
    variable = DiscreteVariable("x", values=("1", "0"))
    domain = Domain([variable], DiscreteVariable("y", values=("1", "0")))
    data = Table.from_numpy(domain, np.array([[0], [1]]), np.array([0, 1]))
    assert task_from_table(data)["outputs"] == [0, 1]


def test_workflow_and_supplied_table_are_loadable():
    from pathlib import Path
    from orangecanvas.registry import WidgetRegistry
    from orangecanvas.scheme import Scheme
    from orangewidget.workflow.discovery import WidgetDiscovery
    root = Path(__file__).resolve().parents[1]
    assert task_from_table(Table(str(root / "exemplos/intuicao_xor.tab")))["outputs"] == [0, 1, 1, 0]
    registry = WidgetRegistry()
    discovery = WidgetDiscovery(registry)
    for package in ("omega_nextorch.orange", "Orange.widgets.data"):
        discovery.process_category_package(package)
    scheme = Scheme()
    with (root / "exemplos/omega_nextorch.ows").open("rb") as stream:
        scheme.load_from(stream, registry=registry)
    assert len(scheme.nodes) == 2 and len(scheme.links) == 1


class TestOmegaWidget(widget_test_base.WidgetTest):
    def setUp(self):
        super().setUp()
        self.widget = self.create_widget(OWOmegaCertifier,
            stored_settings={"epochs": 2, "require_lean": False})

    def test_real_certification_and_replacement(self):
        self.send_signal(self.widget.Inputs.data, truth_table())
        self.widget.apply()
        self.wait_until_finished(self.widget, timeout=30000)
        assert not self.widget.Error.failed.is_shown(), self.widget.Error.failed.formatted
        assert verify(self.get_output(self.widget.Outputs.certificate))
        self.send_signal(self.widget.Inputs.data, None)
        assert self.get_output(self.widget.Outputs.certificate) is None

    def test_partial_specification_has_no_output(self):
        self.send_signal(self.widget.Inputs.data, truth_table()[:2])
        self.widget.apply()
        self.wait_until_finished(self.widget, timeout=30000)
        assert self.widget.Error.failed.is_shown()
        assert self.get_output(self.widget.Outputs.certificate) is None

    def test_category_is_registered(self):
        from importlib.metadata import entry_points
        assert any(p.value == "omega_nextorch.orange" for p in entry_points(group="orange.widgets"))
