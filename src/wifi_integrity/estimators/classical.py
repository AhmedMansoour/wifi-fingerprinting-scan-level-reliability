"""Classical learning estimators used in the benchmark."""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor

from wifi_integrity.estimators.base import BasePositionEstimator, UnitData


class SklearnCoordinateEstimator(BasePositionEstimator):
    def __init__(self, estimator_id: str, estimator_label: str, family: str, model, *, seed: int = 42):
        super().__init__(seed=seed)
        self.estimator_id = estimator_id
        self.estimator_label = estimator_label
        self.family = family
        self.model = model

    def fit(self, data: UnitData) -> "SklearnCoordinateEstimator":
        self.model.fit(data.legacy_train_features, data.train_xy)
        return self

    def predict(self, data: UnitData) -> np.ndarray:
        return np.asarray(self.model.predict(data.legacy_test_features), dtype=float)


def make_random_forest(seed: int = 42) -> SklearnCoordinateEstimator:
    model = RandomForestRegressor(
        n_estimators=80,
        max_depth=18,
        min_samples_leaf=2,
        max_features="sqrt",
        n_jobs=-1,
        random_state=seed,
    )
    return SklearnCoordinateEstimator("random_forest", "Random Forest", "tree_ensemble", model, seed=seed)


def make_extra_trees(seed: int = 42) -> SklearnCoordinateEstimator:
    model = ExtraTreesRegressor(
        n_estimators=250,
        max_features="sqrt",
        min_samples_leaf=2,
        random_state=seed,
        n_jobs=-1,
    )
    return SklearnCoordinateEstimator("extra_trees", "Extra Trees", "tree_ensemble", model, seed=seed)


def make_hgb(seed: int = 42) -> SklearnCoordinateEstimator:
    base = HistGradientBoostingRegressor(
        max_iter=120,
        learning_rate=0.08,
        max_leaf_nodes=31,
        l2_regularization=0.05,
        early_stopping=True,
        random_state=seed,
    )
    model = MultiOutputRegressor(base)
    return SklearnCoordinateEstimator(
        "hgb", "Histogram-Based Gradient Boosting", "boosted_tree", model, seed=seed
    )


def make_catboost(seed: int = 42):
    from .catboost_model import CatBoostCoordinateEstimator
    return CatBoostCoordinateEstimator(seed=seed)
