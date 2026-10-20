import json
from pathlib import Path

import pandas as pd

from wifi_integrity.benchmark.registry import estimator_registry
from wifi_integrity.benchmark.replay import materialize_published_benchmark


def test_estimator_registry_has_eight_estimators():
    registry = estimator_registry(Path("."))
    assert len(registry) == 8
    assert set(registry["estimator_id"]) == {
        "knn", "wknn", "random_forest", "extra_trees", "hgb",
        "catboost", "transformer_ap", "residual_cnn",
    }


def test_published_benchmark_reproduces_approved_results():
    report = materialize_published_benchmark(Path("."))
    assert report["status"] == "passed"
    assert report["prediction_rows"] == 109032
    assert report["query_rows"] == 13629
    assert report["conditions"] == 80
    assert report["max_summary_difference"] < 1e-9
    predictions = pd.read_csv(
        "results/predictions/estimator_predictions_published.csv.gz",
        usecols=["scan_id", "estimator_id", "result_mode"],
    )
    assert predictions["scan_id"].nunique() == 13629
    assert predictions["estimator_id"].nunique() == 8
    assert set(predictions["result_mode"]) == {"published_reference_replay"}
