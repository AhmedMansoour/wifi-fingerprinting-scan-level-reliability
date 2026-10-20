"""Exact published-results replay adapter.

This adapter does not retrain a model. It materializes the frozen, approved
prediction rows so published results can be regression-tested exactly.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


LEGACY_TO_CANONICAL = {
    "KNN": ("knn", "KNN", "retrieval"),
    "WKNN": ("wknn", "WKNN", "retrieval"),
    "Random Forest": ("random_forest", "Random Forest", "tree_ensemble"),
    "Extra Trees": ("extra_trees", "Extra Trees", "tree_ensemble"),
    "Gradient Boosting": ("hgb", "Histogram-Based Gradient Boosting", "boosted_tree"),
    "CatBoost": ("catboost", "CatBoost", "boosted_tree"),
    "Transformer": ("transformer_ap", "AP-token Transformer", "deep"),
    "Residual CNN": ("residual_cnn", "Residual CNN", "deep"),
}


@dataclass(frozen=True)
class FrozenPredictionStore:
    path: Path

    def load(self) -> pd.DataFrame:
        source = pd.read_csv(self.path, dtype={"row_id": str}, low_memory=False)
        missing = sorted(set(source["estimator_display"].unique()) - set(LEGACY_TO_CANONICAL))
        if missing:
            raise ValueError(f"Unmapped approved estimator labels: {missing}")
        canonical = source["estimator_display"].map(LEGACY_TO_CANONICAL)
        source["estimator_id"] = canonical.map(lambda value: value[0])
        source["estimator_label"] = canonical.map(lambda value: value[1])
        source["estimator_family"] = canonical.map(lambda value: value[2])
        source["scan_id"] = source["row_id"].astype(str)
        source["error_2d"] = source["error_m"].astype(float)
        source["result_mode"] = "published_reference_replay"
        return source
