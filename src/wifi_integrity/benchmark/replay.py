"""Materialize and validate the exact approved estimator benchmark."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from wifi_integrity.benchmark.metrics import condition_summary, overall_summary, unit_matrix
from wifi_integrity.estimators.frozen import FrozenPredictionStore


def _unit_lookup(config_path: Path) -> tuple[dict[tuple[str, str], dict], dict[str, dict]]:
    with config_path.open(encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    by_source = {(u["dataset"], u["group"]): u for u in cfg["units"]}
    by_id = {u["id"]: u for u in cfg["units"]}
    return by_source, by_id


def materialize_published_benchmark(root: Path) -> dict:
    root = root.resolve()
    source = root / "reference/approved/legacy_canonical/estimator_predictions_approved.csv.gz"
    by_source, _ = _unit_lookup(root / "config/datasets.yaml")
    pred = FrozenPredictionStore(source).load()
    scans = pd.read_csv(
        root / "reference/public/scan_index.csv.gz",
        usecols=["row_id", "scan_id", "split"],
        dtype={"row_id": str, "scan_id": str},
    )
    scans = scans.loc[scans["split"] == "test", ["row_id", "scan_id"]]
    pred = pred.drop(columns=["scan_id"]).merge(scans, on="row_id", how="left", validate="many_to_one")
    if pred["scan_id"].isna().any():
        raise ValueError("Approved predictions contain row IDs absent from harmonized test scans.")
    mapped = pred.apply(lambda row: by_source[(row["dataset"], row["group"])], axis=1)
    pred["unit_id"] = mapped.map(lambda value: value["id"])
    pred["unit_label"] = mapped.map(lambda value: value["label"])
    columns = [
        "unit_id", "unit_label", "dataset", "group", "scan_id", "estimator_id",
        "estimator_label", "estimator_family", "x_true", "y_true", "x_pred", "y_pred",
        "error_2d", "result_mode", "estimator_name", "transformer_method", "n_tokens", "nearest_rp_distance"
    ]
    output_dir = root / "results/predictions"
    table_dir = root / "results/tables"
    log_dir = root / "results/logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    pred[columns].to_csv(output_dir / "estimator_predictions_published.csv.gz", index=False)
    try:
        pred[columns].to_parquet(output_dir / "estimator_predictions_published.parquet", index=False)
    except Exception:
        pass

    condition = condition_summary(pred[columns])
    overall = overall_summary(condition)
    condition.to_csv(table_dir / "estimator_condition_summary.csv", index=False)
    overall.to_csv(table_dir / "estimator_overall_summary.csv", index=False)
    unit_matrix(condition, "median_error_m").to_csv(table_dir / "estimator_unit_median_matrix.csv")
    unit_matrix(condition, "p90_error_m").to_csv(table_dir / "estimator_unit_p90_matrix.csv")

    approved = pd.read_csv(root / "reference/approved/legacy_canonical/estimator_error_summary.csv")
    label_map = {
        "Gradient Boosting": "Histogram-Based Gradient Boosting",
        "Transformer": "AP-token Transformer",
    }
    approved["estimator_label"] = approved["estimator_display"].replace(label_map)
    merged = overall.merge(
        approved[["estimator_label", "median_of_unit_medians_m", "median_unit_p90_m"]],
        on="estimator_label",
        suffixes=("_recomputed", "_approved"),
        validate="one_to_one",
    )
    merged["abs_diff_median"] = (
        merged["median_of_unit_medians_m_recomputed"]
        - merged["median_of_unit_medians_m_approved"]
    ).abs()
    merged["abs_diff_p90"] = (
        merged["median_unit_p90_m_recomputed"] - merged["median_unit_p90_m_approved"]
    ).abs()
    max_diff = float(merged[["abs_diff_median", "abs_diff_p90"]].to_numpy().max())
    report = {
        "status": "passed" if max_diff < 1e-9 else "failed",
        "mode": "published_reference_replay",
        "prediction_rows": int(len(pred)),
        "query_rows": int(pred["scan_id"].nunique()),
        "units": int(pred["unit_id"].nunique()),
        "estimators": int(pred["estimator_id"].nunique()),
        "conditions": int(len(condition)),
        "max_summary_difference": max_diff,
        "output": str(output_dir / "estimator_predictions_published.csv.gz"),
    }
    (log_dir / "estimator_benchmark_regression_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    merged.to_csv(table_dir / "estimator_benchmark_regression_differences.csv", index=False)
    return report
