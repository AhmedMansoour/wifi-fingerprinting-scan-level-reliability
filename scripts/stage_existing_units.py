"""Prepare the ORIGINAL dataset-unit matrices from authorized, AP-relabeled scans.

This is only format adaptation. It does not fit models, compute indicators, or
replace approved historical results. Files are written to the local ignored
``data/processed`` workspace and are not publication inputs by default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wifi_integrity.data.harmonize import dense_matrix, parse_rss_json, training_ap_vocabulary

AP = re.compile(r"AP[1-9][0-9]*\Z")
COLUMNS = ["dataset", "group", "split", "row_id", "floor", "x", "y", "rss_json"]


def prepare(input_dir: Path, root: Path = ROOT, unit_ids: list[str] | None = None,
            allow_custom_splits: bool = False) -> dict:
    spec = yaml.safe_load((root / "config/datasets.yaml").read_text(encoding="utf-8"))
    units = spec["units"]
    selected = [s for s in units if unit_ids is None or s["id"] in unit_ids]
    if len(selected) != (len(units) if unit_ids is None else len(set(unit_ids))):
        raise ValueError("Unknown or duplicate unit ID")
    info = {}
    for unit in selected:
        uid = unit["id"]
        file = input_dir / (uid + ".csv.gz")
        if not file.is_file():
            raise FileNotFoundError(f"Missing authorized research input {file}")
        frame = pd.read_csv(file, dtype={"row_id": str}, low_memory=False)
        if list(frame.columns) != COLUMNS:
            raise ValueError(f"Wrong schema for {uid}: {frame.columns.tolist()}")
        if not frame["split"].isin(["train", "test"]).all():
            raise ValueError(f"Invalid split in {uid}")
        is_public_hk=(uid == "U09" and frame["dataset"].eq("HK_U09").all()
                      and frame["group"].eq("HK_LOCAL").all())
        if not is_public_hk and not (frame["dataset"].eq(unit["dataset"]) & frame["group"].eq(unit["group"])).all():
            raise ValueError(f"Source registry mismatch {uid}")
        if frame["row_id"].duplicated().any():
            raise ValueError(f"Non-unique scan identifiers in {uid}")
        train = frame.loc[frame.split.eq("train")].copy()
        test = frame.loc[frame.split.eq("test")].copy()
        if not allow_custom_splits and (len(train) != int(unit["expected_train"]) or len(test) != int(unit["expected_test"])):
            raise ValueError(f"Split counts mismatch for {uid}")
        train_json = [parse_rss_json(v) for v in train.rss_json]
        test_json = [parse_rss_json(v) for v in test.rss_json]
        if any(not all(AP.fullmatch(ap) for ap in values) for values in train_json + test_json):
            raise ValueError(f"Invalid RSS/AP namespace for {uid}")
        ap = training_ap_vocabulary(train_json)
        xtr, mtr = dense_matrix(train_json, ap)
        xte, mte = dense_matrix(test_json, ap)
        xy_train = train[["x", "y"]].to_numpy(dtype=float)
        xy_test = test[["x", "y"]].to_numpy(dtype=float)
        if not np.isfinite(xy_train).all() or not np.isfinite(xy_test).all():
            raise ValueError(f"Nonfinite coordinates in {uid}")
        save = root / "data/processed/units" / uid
        save.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(save / "radio_map_matrices.npz",
            train_rss=xtr, train_observed=mtr, test_rss=xte, test_observed=mte,
            train_xy=xy_train, test_xy=xy_test,
            train_scan_id=train.row_id.to_numpy(dtype=str),
            test_scan_id=test.row_id.to_numpy(dtype=str))
        (save / "ap_vocabulary_train.json").write_text(json.dumps(ap, indent=2)+"\n")
        metadata = pd.concat([train, test], ignore_index=True)[["row_id", "split"]].copy()
        metadata.rename(columns={"row_id": "scan_id"}, inplace=True)
        metadata["source_row"] = metadata.groupby("split").cumcount()
        metadata.to_csv(save / "scan_metadata.csv.gz", index=False, compression="gzip")
        info[uid] = {
            "dataset": unit["dataset"], "group": unit["group"],
            "input_sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            "train": len(train), "test": len(test), "training_aps": len(ap),
            "test_only_aps": len(set().union(*(z.keys() for z in test_json)) - set(ap)),
        }
    report = {"mode": "format_only_using_existing_harmonization", "custom_splits": allow_custom_splits, "status": "passed",
              "total_train": sum(v["train"] for v in info.values()),
              "total_test": sum(v["test"] for v in info.values()), "units": info}
    folder = root / "results/logs"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ten_unit_input_staging.json").write_text(json.dumps(report, indent=2)+"\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True, help="Directory containing U01.csv.gz through U10.csv.gz")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--units", nargs="*", help="Optional unit IDs")
    parser.add_argument("--allow-custom-splits", action="store_true",
                        help="Allow original publisher partitions different from the paper; not historic-result reproduction")
    args = parser.parse_args()
    print(json.dumps(prepare(args.input_dir, args.root, args.units, args.allow_custom_splits), indent=2))

if __name__ == "__main__":
    main()
