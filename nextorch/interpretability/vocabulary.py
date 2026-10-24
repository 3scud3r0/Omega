"""User-annotated feature vocabulary; unannotated units have no invented semantics."""

import torch


class FeatureVocabulary:
    def __init__(self, labels=None):
        self.labels = dict(labels or {})

    def annotate(self, index, label):
        if index < 0 or not label.strip():
            raise ValueError("Need a nonnegative index and nonempty label")
        self.labels[int(index)] = label

    def decode(self, features, top_k=5):
        if features.ndim == 1:
            features = features.unsqueeze(0)
        if features.ndim != 2 or top_k <= 0:
            raise ValueError("Need [batch, features] and positive top_k")
        values, indices = features.detach().topk(min(top_k, features.shape[-1]), dim=-1)
        return [
            [
                {
                    "index": int(i),
                    "activation": float(v),
                    "label": self.labels.get(int(i), f"Feature #{int(i)} (unannotated)"),
                }
                for v, i in zip(row_v, row_i)
                if v > 0
            ]
            for row_v, row_i in zip(values, indices)
        ]


def decode_sae_features(features: torch.Tensor, top_k=2):
    return [item["label"] for row in FeatureVocabulary().decode(features, top_k) for item in row]
