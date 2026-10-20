"""Frozen-result regression checks used before refactoring later stages."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from wifi_integrity.reliability.sqs import reconstruct_sqs


class FrozenResultMismatch(AssertionError):
    pass


def validate_frozen_results(root: str | Path = ".") -> dict[str, object]:
    root_path = Path(root)
    scans = pd.read_csv(
        root_path / "data/processed/harmonized_scans.csv.gz",
        usecols=["row_id", "split"],
        dtype={"row_id": str},
    )
    test_ids = set(scans.loc[scans["split"] == "test", "row_id"])

    prediction_path = root_path / "reference/approved/legacy_canonical/estimator_predictions_approved.csv.gz"
    predictions = pd.read_csv(
        prediction_path,
        usecols=["row_id", "estimator_display"],
        dtype={"row_id": str},
    )
    prediction_ids = set(predictions["row_id"])
    if len(predictions) != 109032 or predictions["estimator_display"].nunique() != 8:
        raise FrozenResultMismatch("Approved prediction table cardinality changed")
    if prediction_ids != test_ids:
        raise FrozenResultMismatch("Prediction query IDs do not match harmonized held-out IDs")

    feature_path = root_path / "reference/approved/legacy_canonical/reliability_features_approved.csv.gz"
    features = pd.read_csv(feature_path, dtype={"row_id": str})
    if len(features) != 13629 or not features["row_id"].is_unique:
        raise FrozenResultMismatch("Approved reliability-feature table cardinality changed")
    if set(features["row_id"]) != test_ids:
        raise FrozenResultMismatch("Reliability-feature IDs do not match harmonized held-out IDs")

    reconstructed = reconstruct_sqs(features)
    difference = np.abs(reconstructed.to_numpy() - features["SQS"].to_numpy(dtype=float))
    max_difference = float(np.nanmax(difference))
    if max_difference > 1e-12:
        raise FrozenResultMismatch(f"SQS reconstruction differs by {max_difference}")

    report = {
        "status": "passed",
        "heldout_query_ids": len(test_ids),
        "prediction_rows": len(predictions),
        "estimators": int(predictions["estimator_display"].nunique()),
        "reliability_feature_rows": len(features),
        "sqs_max_absolute_difference": max_difference,
    }
    return report


def write_frozen_result_report(report: dict[str, object], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
