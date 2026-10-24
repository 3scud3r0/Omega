import numpy as np
import pytest
import torch

pytest.importorskip("Orange")
from Orange.data import ContinuousVariable, DiscreteVariable, Domain, StringVariable, Table
from scipy.sparse import csr_matrix

from nextorch.core import OrangeBridge

pytestmark = pytest.mark.orange


def _table():
    domain = Domain(
        [ContinuousVariable("value"), DiscreteVariable("kind", values=["a", "b"])],
        DiscreteVariable("target", values=["no", "yes"]),
        [StringVariable("note")],
    )
    return Table.from_numpy(
        domain,
        np.array([[1.0, 0], [3.0, 1], [np.nan, np.nan]]),
        np.array([0.0, 1.0, 1.0]),
        np.array([["one"], ["two"], ["three"]], dtype=object),
        W=np.array([1.0, 2.0, 3.0]),
        attributes={"source": "test"},
    )


def test_fitted_bridge_imputes_normalizes_encodes_and_reuses_training_statistics():
    table = _table()
    bridge = OrangeBridge()
    x, y = bridge.fit_transform(table)
    torch.testing.assert_close(
        x, torch.tensor([[-1.0, 1.0, 0.0, 0.0], [1.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]])
    )
    assert y.dtype == torch.long and bridge.feature_names == [
        "value",
        "kind=a",
        "kind=b",
        "kind=<missing>",
    ]
    unseen = Table.from_numpy(
        table.domain, np.array([[5.0, 1.0]]), np.array([1.0]), np.array([["unseen"]], dtype=object)
    )
    assert bridge.transform(unseen)[0][0, 0] == 3
    with pytest.raises(ValueError, match="schema"):
        bridge.transform(Table.from_numpy(Domain([ContinuousVariable("other")]), np.ones((2, 1))))


def test_append_preserves_class_meta_weights_ids_and_attributes():
    original = _table()
    features = torch.randn(3, 4)
    output = OrangeBridge.append_features(original, features)
    np.testing.assert_array_equal(output.Y, original.Y)
    np.testing.assert_array_equal(output.metas, original.metas)
    np.testing.assert_array_equal(output.W, original.W)
    np.testing.assert_array_equal(output.ids, original.ids)
    assert (
        output.attributes == original.attributes
        and output.domain.class_vars == original.domain.class_vars
    )
    np.testing.assert_allclose(output.X[:, -4:], features.numpy())
    assert original.X.shape == (3, 2)
    with pytest.raises(ValueError, match="collide"):
        OrangeBridge.append_features(original, features[:, :1], ["value"])


def test_sparse_input_unlabelled_and_all_missing_column():
    table = Table.from_numpy(
        Domain([ContinuousVariable("x"), ContinuousVariable("y")]),
        csr_matrix([[0.0, 1.0], [2.0, 0.0]]),
    )
    x, y = OrangeBridge.table_to_tensors(table)
    assert torch.isfinite(x).all() and y is None
    missing = Table.from_numpy(Domain([ContinuousVariable("empty")]), np.full((3, 1), np.nan))
    assert OrangeBridge.table_to_tensors(missing)[0].abs().sum() == 0


def test_tensors_to_table_and_missing_class_labels():
    table = _table()
    with table.unlocked(table.Y):
        table.Y[0] = np.nan
    x, y = OrangeBridge.table_to_tensors(table)
    assert y.is_floating_point() and torch.isnan(y[0])
    converted = OrangeBridge.tensors_to_table(x, [f"x{i}" for i in range(4)])
    np.testing.assert_allclose(converted.X, x.numpy())
    with pytest.raises(ValueError):
        OrangeBridge.tensors_to_table(x, ["bad"])


def test_model_persistence_restores_fitted_preprocessing_and_sae(tmp_path):
    from nextorch.model import NextorchModel

    table = _table()
    model = NextorchModel.from_table(table, width=8, candidates=1)
    x, y = model.bridge.transform(table)
    model.fit(x, y, epochs=3)
    expected = model(x).detach()
    path = tmp_path / "tabular.pt"
    model.save(path)
    loaded = NextorchModel.load(path)
    x_again, _ = loaded.bridge.transform(table)
    torch.testing.assert_close(x_again, x)
    torch.testing.assert_close(loaded(x_again), expected)
    assert loaded.trained_steps == 3
