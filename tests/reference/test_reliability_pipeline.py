import json
from pathlib import Path

import numpy as np
import pandas as pd

from wifi_integrity.reliability.sqs import reconstruct_sqs


def test_reliability_feature_outputs_and_sqs_regression():
    native = pd.read_csv("results/reliability/reliability_features_native.csv.gz")
    published = pd.read_csv("results/reliability/reliability_features_published.csv.gz")
    candidates = pd.read_csv("results/reliability/diagnostic_candidates_m10.csv.gz")
    assert len(native) == 13629
    assert len(published) == 13629
    assert len(candidates) == 136290
    assert candidates["candidate_rank"].min() == 1
    assert candidates["candidate_rank"].max() == 10
    reconstructed = reconstruct_sqs(published)
    difference = np.abs(reconstructed.to_numpy() - published["SQS"].to_numpy())
    assert np.nanmax(difference) < 1e-12


def test_reliability_feature_report_has_explicit_provenance():
    report = json.loads(
        Path("results/logs/reliability_feature_regression_report.json").read_text()
    )
    assert report["feature_rows"] == 13629
    assert report["candidate_rows"] == 136290
    regression = report["reference_regression"]
    assert regression["matched_rows"] == 13629
    assert regression["published_sqs_reconstruction_n_difference_gt_1e_12"] == 0
    assert "tie" in regression["note"].lower()


def test_reliability_analysis_regression():
    report = json.loads(
        Path("results/logs/reliability_analysis_regression_report.json").read_text()
    )
    assert report["long_rows"] == 109032
    assert report["association_condition_rows"] == 1440
    assert report["valid_association_tests"] == 1429
    assert report["threshold_conditions"] == 80
    assert report["max_abs_association_median_difference"] < 1e-12
    association = pd.read_csv("results/tables/reliability_association_by_condition.csv")
    discrimination = pd.read_csv("results/tables/gross_error_discrimination_by_condition.csv")
    assert len(association) == 1440
    assert set(discrimination["strategy"]) == {"adaptive_iqr", "fixed_7m"}


def test_case_registry_and_candidate_linkage():
    registry = pd.read_csv("results/cases/case_registry.csv")
    candidates = pd.read_csv("results/cases/case_candidates.csv")
    report = json.loads(Path("results/cases/case_selection_report.json").read_text())
    assert len(registry) == 24
    assert len(candidates) == 240
    assert registry["case_id"].is_unique
    assert candidates.groupby("case_id").size().eq(10).all()
    assert report["represented_units"] >= 6
    assert report["represented_estimators"] == 8
    assert {"confidently_wrong", "detected_or_low_confidence_gross_error"}.issubset(
        set(registry["case_state"])
    )
