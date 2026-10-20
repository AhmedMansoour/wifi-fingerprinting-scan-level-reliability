from pathlib import Path
import zipfile

import yaml
import pytest


def test_frozen_archive_contains_approved_tables():
    archive = Path("legacy_release/data/scratch_start.zip")
    if not archive.is_file():
        pytest.skip("Private frozen archive is not included in the lightweight source package.")
    required = {
        "scratch_start/data/processed/all_estimator_predictions_10like_units_plus_catboost.csv.gz",
        "scratch_start/data/processed/scan_level_reliability_indicator_features.csv.gz",
        "scratch_start/results/tables/indicator_error_association_summary.csv",
    }
    with zipfile.ZipFile(archive) as zf:
        assert required.issubset(set(zf.namelist()))


def test_headline_reference_values_are_locked():
    with Path("reference/approved/headline_values.yaml").open(encoding="utf-8") as handle:
        reference = yaml.safe_load(handle)
    assert reference["sample_counts"]["heldout_queries"] == 13629
    assert reference["sample_counts"]["estimators"] == 8
    assert reference["sample_counts"]["indicators"] == 18
    assert reference["sqs"]["adaptive_median_auroc"] == 0.768750


def test_approved_prediction_and_feature_cardinality():
    import pandas as pd

    pred = pd.read_csv(
        "reference/approved/legacy_canonical/estimator_predictions_approved.csv.gz",
        usecols=["row_id", "estimator_display"],
    )
    features = pd.read_csv(
        "reference/approved/legacy_canonical/reliability_features_approved.csv.gz",
        usecols=["row_id"],
    )
    assert len(pred) == 109032
    assert pred["estimator_display"].nunique() == 8
    assert pred["row_id"].nunique() == 13629
    assert len(features) == 13629
    assert features["row_id"].is_unique
