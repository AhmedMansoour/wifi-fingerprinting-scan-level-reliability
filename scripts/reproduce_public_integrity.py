"""Compute scan-level integrity on public measured units using the original indicators.

This module never substitutes archived reference results: its `results/public_integrity/`
outputs are fresh calculations. U09 uses original-order published training/test data.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wifi_integrity.data.registry import load_registry
from wifi_integrity.reliability.indicators import _unit_features, K_LARGE
from wifi_integrity.reliability.sqs import reconstruct_sqs

PUBLIC_UNITS = ("U01", "U02", "U03", "U09")
FIELDS = ("dataset", "group", "split", "row_id", "floor", "x", "y", "rss_json")


def input_files(root: Path, unit_id: str) -> list[Path]:
    if unit_id == "U09":
        return [root / "data/radio_maps/hk_u09_train.csv.gz",
                root / "data/empirical/hk_u09_test_ordered.csv.gz"]
    if unit_id in PUBLIC_UNITS:
        return [root / "data/empirical" / f"{unit_id}.csv.gz"]
    raise ValueError(f"Not publicly hosted: {unit_id}; use documented local inputs separately")


def _read_unit(root: Path, unit_id: str, spec):
    sources = input_files(root, unit_id)
    frames = []
    for source in sources:
        if not source.is_file():
            raise FileNotFoundError(f"Missing public empirical file: {source}")
        frame = pd.read_csv(source, dtype={"row_id": "str"}, low_memory=False)
        if list(frame.columns) != list(FIELDS):
            raise ValueError(f"Unexpected canonical columns in {source}")
        if frame["row_id"].isna().any() or frame["row_id"].duplicated().any():
            raise ValueError(f"Invalid scan IDs in {source}")
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    if data.row_id.duplicated().any():
        raise ValueError(f"Nonunique scan ID in {unit_id}")
    if not data["split"].isin(["train", "test"]).all():
        raise ValueError(f"Unsupported split label in {unit_id}")
    if unit_id == "U09":
        if not (((data.dataset.eq("HK_U09") & data.group.eq("HK_LOCAL")) |
                 (data.dataset.eq(spec.dataset) & data.group.eq(spec.group))).all()):
            raise ValueError("Published U09 source identifiers do not match the recognized aliases")
        # Preserve public anonymous HK aliases for output metadata, not the source's site label.
        data.loc[:, "dataset"] = "HK_U09"
        data.loc[:, "group"] = "HK_LOCAL"
    elif not (data.dataset.eq(spec.dataset) & data.group.eq(spec.group)).all():
        raise ValueError(f"Dataset/group mismatch in {unit_id}")
    train = int(data.split.eq("train").sum()); test = int(data.split.eq("test").sum())
    if (train, test) != (spec.expected_train, spec.expected_test):
        raise ValueError(f"Study split count mismatch for {unit_id}: {train}/{test}")
    fingerprints = data.loc[:, ["row_id", "split", "floor", "x", "y"]]
    if not (np.isfinite(pd.to_numeric(fingerprints["x"]).to_numpy()).all() and
            np.isfinite(pd.to_numeric(fingerprints["y"]).to_numpy()).all()):
        raise ValueError(f"Invalid relative location for {unit_id}")
    return data, sources, train, test


def run(root: Path = ROOT, units: list[str] | tuple[str, ...] = PUBLIC_UNITS,
        output: Path | None = None, *, write: bool = True) -> dict:
    root = Path(root).resolve()
    selected = list(units)
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("Select distinct public units")
    unknown = set(selected) - set(PUBLIC_UNITS)
    if unknown:
        raise ValueError(f"Unpublished unit inputs: {', '.join(sorted(unknown))}")
    registry = {u.id: u for u in load_registry(root / "config/datasets.yaml")}
    output = Path(output or root / "results/public_integrity").resolve()
    summaries = {}
    for unit_id in selected:
        spec = registry[unit_id]
        data, sources, ntrain, ntest = _read_unit(root, unit_id, spec)
        if unit_id == "U09":
            spec = replace(spec, dataset="HK_U09", group="HK_LOCAL")
        # Reuse original scientific implementation without reimplementing indicators.
        features, candidates = _unit_features(root, spec, data)
        if len(features) != ntest or len(candidates) != K_LARGE * ntest:
            raise AssertionError(f"Incorrect output size for {unit_id}")
        if features["row_id"].duplicated().any():
            raise AssertionError(f"Repeated test scan for {unit_id}")
        expected_ids = set(data.loc[data.split.eq("test"), "row_id"].astype(str))
        if set(features.row_id.astype(str)) != expected_ids:
            raise AssertionError(f"Test scan misalignment in {unit_id}")
        sqs = reconstruct_sqs(features)
        diff = np.abs(sqs.to_numpy(dtype=float) - features["SQS"].to_numpy(dtype=float))
        if not np.isfinite(diff).all() or diff.max(initial=0.0) > 1e-12:
            raise AssertionError(f"SQS reconstruction failed on {unit_id}")
        if not np.isfinite(features["SQS"]).all() or not features["SQS"].between(0, 1).all():
            raise AssertionError(f"Invalid SQS range on {unit_id}")
        summary = {
            "unit": unit_id,
            "status": "computed_from_public_measurements",
            "train_scans": ntrain,
            "test_scans": ntest,
            "scan_level_feature_rows": len(features),
            "retrieved_candidate_rows": len(candidates),
            "sqs_mean": float(features.SQS.mean()),
            "sqs_median": float(features.SQS.median()),
            "sqs_max_reconstruction_delta": float(diff.max(initial=0.0)),
            "input_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        }
        if write:
            output.mkdir(parents=True, exist_ok=True)
            features.to_csv(output / f"{unit_id}_scan_reliability.csv.gz", index=False, compression="gzip")
            candidates.to_csv(output / f"{unit_id}_retrieved_candidates.csv.gz", index=False, compression="gzip")
        summaries[unit_id] = summary
    report = {
        "status": "passed", "scope": "new native indicator and SQS recomputation, not an exact historical replay",
        "units": summaries,
        "total_scan_features": sum(v["scan_level_feature_rows"] for v in summaries.values()),
        "total_candidate_rows": sum(v["retrieved_candidate_rows"] for v in summaries.values()),
        "historical_8_estimator_retraining": False,
        "gross_error_ground_truth_classification_run": False,
    }
    if write:
        (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--units", nargs="+", choices=PUBLIC_UNITS, default=list(PUBLIC_UNITS))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.units, args.output), indent=2))


if __name__ == "__main__":
    main()
