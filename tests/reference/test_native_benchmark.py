from pathlib import Path

import pandas as pd

from wifi_integrity.benchmark.native import run_native_benchmark


def test_native_retrieval_smoke_matches_dsi_reference():
    report = run_native_benchmark(
        Path("."),
        unit_ids=["U10"],
        estimator_ids=["knn", "wknn"],
        output_name="test_native_retrieval.csv.gz",
    )
    assert report["status"] == "completed"
    assert report["prediction_rows"] == 686
    native = pd.read_csv("results/tables/test_native_retrieval_condition_summary.csv")
    approved = pd.read_csv("results/tables/estimator_condition_summary.csv")
    approved = approved[(approved["unit_id"] == "U10") & approved["estimator_id"].isin(["knn", "wknn"])]
    merged = native.merge(
        approved[["estimator_id", "median_error_m"]],
        on="estimator_id",
        suffixes=("_native", "_approved"),
    )
    assert (merged["median_error_m_native"] - merged["median_error_m_approved"]).abs().max() < 1e-9
