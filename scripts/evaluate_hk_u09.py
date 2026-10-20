"""Run real held-out HK U09 2D positioning using the repository's estimator classes.

No floor/ground truth is supplied at inference. This is a new, explicitly specified
baseline run on the AP-renamed relative-coordinate data, not a historic-paper replay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wifi_integrity.benchmark.metrics import summarize_condition
from wifi_integrity.data.harmonize import dense_matrix, parse_rss_json, training_ap_vocabulary
from wifi_integrity.estimators.base import UnitData
from wifi_integrity.estimators.classical import make_random_forest
from wifi_integrity.estimators.retrieval import RetrievalEstimator

DEFAULT_INPUT = ROOT / "data/empirical/hk_u09_ap_relative.csv.gz"
EXPECTED_HASH = "b99bac3454e8f0f306c7fb8c012a7def5e277251c8013304e50e02ae51717078"


def load_u09(input_file: Path, *, check_hash: bool = True) -> tuple[UnitData, pd.DataFrame, dict]:
    input_file = Path(input_file)
    actual_hash = hashlib.sha256(input_file.read_bytes()).hexdigest()
    if check_hash and actual_hash != EXPECTED_HASH:
        raise ValueError("HK U09 input digest is not the reviewed release")
    frame = pd.read_csv(input_file, dtype={"row_id": str}, low_memory=False)
    expected_cols = {"dataset", "group", "split", "row_id", "floor", "x", "y", "rss_json"}
    if set(frame.columns) != expected_cols:
        raise ValueError("Unexpected data columns")
    if not frame.split.isin(["train", "test"]).all():
        raise ValueError("Unrecognized split")
    train = frame.loc[frame.split.eq("train")].copy()
    test = frame.loc[frame.split.eq("test")].copy()
    if len(train) < 2 or len(test) < 1:
        raise ValueError("Insufficient training or test observations")
    if train.row_id.duplicated().any() or test.row_id.duplicated().any():
        raise ValueError("Duplicate scan identifiers")
    if set(train.row_id).intersection(test.row_id):
        raise ValueError("Leaked scan identifiers across splits")
    train_dict = [parse_rss_json(v) for v in train.rss_json]
    test_dict = [parse_rss_json(v) for v in test.rss_json]
    vocab = training_ap_vocabulary(train_dict)  # Deliberately NEVER constructed from test scans
    if not vocab:
        raise ValueError("Empty training AP vocabulary")
    xtr, mtr = dense_matrix(train_dict, vocab)
    xte, mte = dense_matrix(test_dict, vocab)
    xytr = train[["x", "y"]].to_numpy(dtype=float)
    xyte = test[["x", "y"]].to_numpy(dtype=float)
    if not np.isfinite(xytr).all() or not np.isfinite(xyte).all():
        raise ValueError("Nonfinite coordinates")
    unit = UnitData(
        unit_id="U09", unit_label="HK U09 relative", dataset="HK_U09", group="HK_LOCAL",
        train_rss=xtr, train_observed=mtr, test_rss=xte, test_observed=mte,
        train_xy=xytr, test_xy=xyte, train_scan_id=train.row_id.to_numpy(),
        test_scan_id=test.row_id.to_numpy(), ap_names=tuple(vocab),
    )
    meta = {
        "input_sha256": actual_hash,
        "train_scans": int(len(train)), "test_scans": int(len(test)),
        "training_ap_vocabulary": len(vocab),
        "test_only_ap_count": len(set().union(*(d.keys() for d in test_dict)) - set(vocab)),
        "floor_labels_in_test": sorted(int(x) for x in test.floor.unique()),
        "missing_ap_handling": "-110 dBm stored; repository legacy estimator feature view zero-masks unobserved APs",
        "split_origin": "published input split column, no resplitting",
    }
    return unit, test, meta


def evaluate(input_file: Path = DEFAULT_INPUT, *, estimators: tuple[str, ...] = ("knn", "wknn", "random_forest"), k: int = 5,
             weight_power: float = 2.0, seed: int = 42, check_hash: bool = True) -> tuple[dict, pd.DataFrame]:
    if k < 1:
        raise ValueError("k must be positive")
    unit, test, meta = load_u09(input_file, check_hash=check_hash)
    if k > len(unit.train_xy):
        raise ValueError("k exceeds training rows")
    runs = []
    summary = {}
    allowed = {"knn", "wknn", "random_forest"}
    if not estimators or len(set(estimators)) != len(estimators) or not set(estimators) <= allowed:
        raise ValueError("Invalid or repeated estimator IDs")
    for eid in estimators:
        if eid == "knn":
            est = RetrievalEstimator(estimator_id="knn", estimator_label="KNN", k=k, metric="euclidean", seed=seed)
        elif eid == "wknn":
            est = RetrievalEstimator(estimator_id="wknn", estimator_label="WKNN", k=k, metric="euclidean",
                                     weight_power=weight_power, seed=seed)
        else:
            est = make_random_forest(seed=seed)
        run = est.fit_predict(unit)
        pred = run.predictions.copy()
        if len(pred) != len(test) or not np.isfinite(pred.error_2d).all():
            raise ValueError("Invalid estimator predictions")
        pred["floor_true"] = test.floor.to_numpy(dtype=int)
        runs.append(pred)
        stats = summarize_condition(pred)
        summary[eid] = {
            "estimator_label": est.estimator_label,
            "n_test": int(stats["n_test"]),
            **{name: round(float(stats[name]), 6) for name in ["mean_error_m", "median_error_m", "rmse_error_m", "p75_error_m", "p90_error_m", "p95_error_m", "max_error_m"]},
        }
    results = pd.concat(runs, ignore_index=True)
    # Summaries use held-out reference coordinates only AFTER making every prediction.
    report = {
        "evaluation_type": "new held-out empirical HK U09 baseline, not paper-result replay",
        "data_source": "published AP-renamed measured HK U09 RSS and relative metric XY",
        "protocol": "fixed original train/test split; train-only AP vocabulary; 2D floor-agnostic estimation",
        "settings": {"k": k, "wknn_inverse_distance_power": weight_power, "seed": seed,
                     "metric": "euclidean", "estimators": list(estimators)},
        "input": meta,
        "estimator_results": summary,
        "limitations": [
            "The target floor is not supplied to estimators; 2D error cannot quantify wrong-floor decisions.",
            "Original benchmark tuning, feature selection, seeds and all eight models are not reconstructed.",
            "Repeated scans, locations and nearby radio fingerprints can make per-scan outcomes correlated.",
            "This dataset covers one published empirical unit, not all ten evaluation units.",
        ],
    }
    return report, results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/empirical/hk_u09")
    parser.add_argument("--estimators", nargs="+", choices=["knn", "wknn", "random_forest"],
                        default=["knn", "wknn", "random_forest"])
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--weight-power", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-input-hash-check", action="store_true", help="Only for independent test fixtures")
    parser.add_argument("--save-predictions", action="store_true", help="Write per-scan predictions locally (ignored)")
    parser.add_argument("--check-frozen", action="store_true", help="Check reproducible reported aggregates")
    args = parser.parse_args()
    report, predictions = evaluate(args.input, estimators=tuple(args.estimators), k=args.k,
                                  weight_power=args.weight_power, seed=args.seed,
                                  check_hash=not args.skip_input_hash_check)
    if args.check_frozen:
        frozen = json.loads((ROOT / "docs/hk_u09_expected_summary.json").read_text())
        if report["input"]["input_sha256"] != frozen["input_sha256"] or report["settings"] != frozen["settings"]:
            raise SystemExit("HK U09 run does not match the frozen input/configuration")
        for eid, expected_metrics in frozen["estimator_results"].items():
            if eid not in report["estimator_results"]:
                raise SystemExit("Missing a baseline estimator: " + eid)
            for metric, value in expected_metrics.items():
                observed = report["estimator_results"][eid][metric]
                if not np.isclose(float(observed), float(value), rtol=0, atol=0.03):
                    raise SystemExit(f"Baseline drift: {eid}/{metric}, observed={observed} expected={value}")
        print("PASS: frozen U09 baseline numerical aggregates reproduced")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.save_predictions:
        predictions.to_csv(args.output_dir / "predictions.csv.gz", index=False, compression="gzip")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
