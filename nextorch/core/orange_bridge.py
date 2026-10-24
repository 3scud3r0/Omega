"""Fitted Orange preprocessing and metadata-preserving feature export.

Orange is optional: it is imported only when a bridge operation needs it.
Discrete attributes become one-hot columns, including a missing-value indicator.
Continuous missing values use the training mean (zero for an all-missing column).
"""

from dataclasses import dataclass

import numpy as np
import torch


def _orange():
    try:
        from Orange.data import ContinuousVariable, Domain, Table
    except ImportError as exc:
        raise RuntimeError("Install nextorch-ai[orange] to use OrangeBridge") from exc
    return Table, Domain, ContinuousVariable


@dataclass
class ColumnState:
    name: str
    values: tuple
    mean: float = 0.0
    scale: float = 1.0


class OrangeBridge:
    def __init__(self):
        self.columns = None
        self.feature_names = []

    @staticmethod
    def _dense(table):
        return table.X.toarray() if hasattr(table.X, "toarray") else np.asarray(table.X)

    def fit_transform(self, table):
        _orange()
        if len(table) == 0 or len(table.domain.attributes) == 0:
            raise ValueError("Need a table with rows and attributes")
        raw = self._dense(table)
        self.columns, self.feature_names = [], []
        for i, var in enumerate(table.domain.attributes):
            if var.is_discrete:
                values = tuple(var.values)
                self.columns.append(ColumnState(var.name, values))
                self.feature_names.extend([f"{var.name}={v}" for v in (*values, "<missing>")])
            elif var.is_continuous:
                finite = raw[:, i][np.isfinite(raw[:, i])]
                mean = float(finite.mean()) if len(finite) else 0.0
                scale = float(finite.std()) if len(finite) else 1.0
                self.columns.append(ColumnState(var.name, (), mean, max(scale, 1e-8)))
                self.feature_names.append(var.name)
            else:
                raise ValueError(f"Unsupported attribute {var.name}")
        return self.transform(table)

    def transform(self, table):
        if self.columns is None:
            raise RuntimeError("Fit the bridge before calling transform")
        attrs = table.domain.attributes
        schema = [(v.name, tuple(v.values) if v.is_discrete else ()) for v in attrs]
        if schema != [(c.name, c.values) for c in self.columns]:
            raise ValueError("Table schema differs from the fitted schema")
        raw, blocks = self._dense(table), []
        for i, state in enumerate(self.columns):
            col = raw[:, i]
            if state.values:
                valid = np.isfinite(col) & (col >= 0) & (col < len(state.values))
                valid &= col == np.floor(np.where(np.isfinite(col), col, -1))
                indices = np.full(len(col), len(state.values), dtype=int)
                indices[valid] = col[valid].astype(int)
                blocks.append(np.eye(len(state.values) + 1, dtype=np.float32)[indices])
            else:
                col = np.where(np.isfinite(col), col, state.mean)
                blocks.append(((col - state.mean) / state.scale)[:, None])
        x = torch.from_numpy(np.concatenate(blocks, axis=1).astype(np.float32))
        y = None
        if table.domain.class_vars:
            y_np = np.asarray(table.Y)
            discrete = all(v.is_discrete for v in table.domain.class_vars)
            dtype = torch.long if discrete and np.isfinite(y_np).all() else torch.float32
            y = torch.tensor(y_np, dtype=dtype)
        return x, y

    @staticmethod
    def table_to_tensors(table):
        return OrangeBridge().fit_transform(table)

    @staticmethod
    def tensors_to_table(x, feature_names):
        Table, Domain, ContinuousVariable = _orange()
        if x.ndim != 2 or x.shape[1] != len(feature_names):
            raise ValueError("Feature names must match tensor columns")
        if len(set(feature_names)) != len(feature_names):
            raise ValueError("Feature names must be unique")
        return Table.from_numpy(
            Domain([ContinuousVariable(n) for n in feature_names]), x.detach().cpu().numpy()
        )

    @staticmethod
    def append_features(table, features, feature_names=None):
        Table, Domain, ContinuousVariable = _orange()
        if features.ndim != 2 or features.shape[0] != len(table):
            raise ValueError("Feature rows must match the original table")
        names = feature_names or [f"SAE_{i}" for i in range(features.shape[1])]
        if len(names) != features.shape[1] or len(set(names)) != len(names):
            raise ValueError("Invalid feature names")
        used = {v.name for v in table.domain.variables + table.domain.metas}
        if used.intersection(names):
            raise ValueError("Derived feature names collide with the original domain")
        domain = Domain(
            list(table.domain.attributes) + [ContinuousVariable(n) for n in names],
            table.domain.class_vars,
            table.domain.metas,
        )
        x = np.column_stack((OrangeBridge._dense(table), features.detach().cpu().numpy()))
        result = Table.from_numpy(
            domain,
            x,
            table.Y.copy(),
            table.metas.copy(),
            W=table.W.copy(),
            attributes=dict(table.attributes),
            ids=table.ids.copy(),
        )
        result.name = table.name
        return result
