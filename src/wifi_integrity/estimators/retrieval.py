"""KNN and inverse-distance-weighted KNN estimators."""
from __future__ import annotations

import numpy as np
from sklearn.neighbors import NearestNeighbors

from wifi_integrity.estimators.base import BasePositionEstimator, UnitData


class RetrievalEstimator(BasePositionEstimator):
    family = "retrieval"

    def __init__(
        self,
        *,
        estimator_id: str,
        estimator_label: str,
        k: int,
        metric: str,
        weight_power: float | None = None,
        epsilon: float = 1e-6,
        seed: int = 42,
    ) -> None:
        super().__init__(seed=seed)
        self.estimator_id = estimator_id
        self.estimator_label = estimator_label
        self.k = int(k)
        self.metric = metric
        self.weight_power = weight_power
        self.epsilon = float(epsilon)
        self._nn: NearestNeighbors | None = None

    def fit(self, data: UnitData) -> "RetrievalEstimator":
        self._nn = NearestNeighbors(n_neighbors=self.k, metric=self.metric, n_jobs=-1)
        self._nn.fit(data.legacy_train_features)
        return self

    def predict(self, data: UnitData) -> np.ndarray:
        if self._nn is None:
            raise RuntimeError("Estimator must be fitted before prediction.")
        distances, indices = self._nn.kneighbors(data.legacy_test_features)
        coords = data.train_xy[indices]
        if self.weight_power is None:
            return coords.mean(axis=1)
        weights = 1.0 / np.power(distances + self.epsilon, self.weight_power)
        weights /= weights.sum(axis=1, keepdims=True)
        return np.sum(coords * weights[:, :, None], axis=1)
