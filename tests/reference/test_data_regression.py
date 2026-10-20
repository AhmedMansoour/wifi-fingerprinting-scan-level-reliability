from pathlib import Path

import pandas as pd

from wifi_integrity.data.registry import load_registry
from wifi_integrity.data.validate import validate_unit_audit


def test_approved_unit_counts_regression():
    audit_path = Path("data/processed/unit_harmonization_audit.csv")
    assert audit_path.is_file(), "Run `python -m wifi_integrity stage-data` first."
    units = load_registry("config/datasets.yaml")
    report = validate_unit_audit(audit_path, units)
    assert report == {
        "status": "passed",
        "units": 10,
        "train_rows": 54520,
        "test_rows": 13629,
        "total_rows": 68149,
    }


def test_canonical_scan_ids_are_unique():
    path = Path("data/processed/harmonized_scans.csv.gz")
    scans = pd.read_csv(path, usecols=["scan_id", "split", "unit_id"])
    assert len(scans) == 68149
    assert scans["scan_id"].is_unique
    assert set(scans["split"]) == {"train", "test"}
    assert scans["unit_id"].nunique() == 10


def test_heldout_row_ids_link_to_approved_outputs():
    test_scans = pd.read_csv(
        "data/processed/harmonized_scans.csv.gz",
        usecols=["row_id", "split"],
        dtype={"row_id": str},
    )
    test_ids = set(test_scans.loc[test_scans["split"] == "test", "row_id"])
    predictions = pd.read_csv(
        "reference/approved/legacy_canonical/estimator_predictions_approved.csv.gz",
        usecols=["row_id"],
        dtype={"row_id": str},
    )
    features = pd.read_csv(
        "reference/approved/legacy_canonical/reliability_features_approved.csv.gz",
        usecols=["row_id"],
        dtype={"row_id": str},
    )
    assert set(predictions["row_id"]) == test_ids
    assert set(features["row_id"]) == test_ids
