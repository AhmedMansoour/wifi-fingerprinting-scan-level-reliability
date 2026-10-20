"""Estimator benchmark metrics and summaries."""
from __future__ import annotations

import numpy as np
import pandas as pd


def summarize_condition(group: pd.DataFrame) -> pd.Series:
    error = group["error_2d"].to_numpy(dtype=float)
    return pd.Series(
        {
            "n_test": len(error),
            "mean_error_m": float(np.mean(error)),
            "median_error_m": float(np.median(error)),
            "rmse_error_m": float(np.sqrt(np.mean(error**2))),
            "p75_error_m": float(np.percentile(error, 75)),
            "p90_error_m": float(np.percentile(error, 90)),
            "p95_error_m": float(np.percentile(error, 95)),
            "max_error_m": float(np.max(error)),
        }
    )


def condition_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    keys = [
        "unit_id",
        "unit_label",
        "dataset",
        "group",
        "estimator_id",
        "estimator_label",
        "estimator_family",
        "result_mode",
    ]
    return (
        predictions.groupby(keys, dropna=False, sort=True)
        .apply(summarize_condition, include_groups=False)
        .reset_index()
    )


def overall_summary(condition: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in condition.groupby(
        ["estimator_id", "estimator_label", "estimator_family", "result_mode"], sort=True
    ):
        rows.append(
            {
                "estimator_id": keys[0],
                "estimator_label": keys[1],
                "estimator_family": keys[2],
                "result_mode": keys[3],
                "units_covered": int(group["unit_id"].nunique()),
                "median_of_unit_medians_m": float(group["median_error_m"].median()),
                "mean_of_unit_medians_m": float(group["median_error_m"].mean()),
                "median_unit_p90_m": float(group["p90_error_m"].median()),
                "median_unit_max_m": float(group["max_error_m"].median()),
                "median_unit_rmse_m": float(group["rmse_error_m"].median()),
            }
        )
    return pd.DataFrame(rows).sort_values("median_of_unit_medians_m").reset_index(drop=True)


def unit_matrix(condition: pd.DataFrame, metric: str) -> pd.DataFrame:
    return condition.pivot(index="unit_label", columns="estimator_label", values=metric)
