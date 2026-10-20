"""Canonical schemas used by the reproducible pipeline."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PredictionKey:
    unit_id: str
    scan_id: str
    estimator_id: str


HARMONIZED_SCAN_COLUMNS = {
    "unit_id",
    "unit_label",
    "scan_id",
    "dataset",
    "group",
    "split",
    "x",
    "y",
    "floor",
    "rss_json",
    "rss_count",
}

CANONICAL_PREDICTION_COLUMNS = {
    "unit_id",
    "scan_id",
    "estimator_id",
    "x_true",
    "y_true",
    "x_pred",
    "y_pred",
    "error_2d",
}

RELIABILITY_BASE_COLUMNS = {
    "unit_id",
    "scan_id",
    "estimator_id",
    "error_2d",
    "floor_true",
}
