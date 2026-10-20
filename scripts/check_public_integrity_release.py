"""Verify that stored public native indicator results have correct scope and provenance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wifi_integrity.reliability.sqs import reconstruct_sqs

COUNTS = {"U01": 1157, "U02": 1101, "U03": 1952, "U09": 831}
EXPECTED_CANDIDATES = 10


def validate(root: Path = ROOT, *, check_fresh: bool = False) -> dict:
    root = Path(root).resolve()
    folder = root / "examples/empirical_integrity"
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    if summary["status"] != "passed" or set(summary["units"]) != set(COUNTS):
        raise AssertionError("Invalid public empirical scope")
    if summary["historical_8_estimator_retraining"] or summary["gross_error_ground_truth_classification_run"]:
        raise AssertionError("Results incorrectly labeled as historical or threshold results")
    output = {"status": "passed", "scan_level_rows": 0, "candidate_rows": 0, "units": {}}
    mac = re.compile(r"(?<![a-fA-F0-9])(?:[a-fA-F0-9]{2}[:-]){5}[a-fA-F0-9]{2}(?![a-fA-F0-9])")
    for uid, expected in COUNTS.items():
        paths = [folder / f"{uid}_scan_reliability.csv.gz", folder / f"{uid}_retrieved_candidates.csv.gz"]
        if any(not path.is_file() for path in paths):
            raise FileNotFoundError(f"Missing native output for {uid}")
        for path in paths:
            if mac.search(path.read_bytes().decode('latin-1')):
                raise AssertionError(f"Unexpected MAC-like bytes in {path}")
        features = pd.read_csv(paths[0], dtype={"row_id": str})
        candidates = pd.read_csv(paths[1], dtype={"row_id": str})
        if len(features) != expected or len(candidates) != expected * EXPECTED_CANDIDATES:
            raise AssertionError(f"Incorrect output counts for {uid}")
        if features.row_id.duplicated().any() or set(candidates.row_id) != set(features.row_id):
            raise AssertionError(f"Scan keys do not align for {uid}")
        if not candidates.groupby("row_id")["candidate_rank"].agg(lambda x: set(x) == set(range(1, EXPECTED_CANDIDATES + 1))).all():
            raise AssertionError(f"Candidate ranks invalid for {uid}")
        sqs_recon = reconstruct_sqs(features)
        delta = np.abs(sqs_recon.to_numpy(dtype=float) - features.SQS.to_numpy(dtype=float))
        if not np.isfinite(delta).all() or delta.max(initial=0.0) > 1e-11:
            raise AssertionError(f"SQS arithmetic mismatch for {uid}")
        if abs(float(features.SQS.median()) - summary["units"][uid]["sqs_median"]) > 1e-10:
            raise AssertionError(f"Frozen SQS summary inconsistent with stored output for {uid}")
        if uid == "U09" and not (features.dataset.eq("HK_U09") & features.group.eq("HK_LOCAL")).all():
            raise AssertionError("HK public aliases missing")
        for path in paths:
            assert path.stat().st_size > 0
        if check_fresh and uid == "U09":
            regenerated = root / "results/public_integrity/U09_scan_reliability.csv.gz"
            if not regenerated.is_file():
                raise FileNotFoundError("Fresh U09 output absent; run reproduce_public_integrity.py first")
            calc = pd.read_csv(regenerated, dtype={"row_id": str})
            merged = features[["row_id", "SQS"]].merge(calc[["row_id", "SQS"]], on="row_id", suffixes=("_stored", "_fresh"), validate="one_to_one")
            if len(merged) != expected or np.abs(merged.SQS_stored - merged.SQS_fresh).max() > 1e-7:
                raise AssertionError("Fresh U09 SQS differs from stored public native result")
        output["units"][uid] = {"features": len(features), "candidates": len(candidates)}
        output["scan_level_rows"] += len(features)
        output["candidate_rows"] += len(candidates)
    if output["scan_level_rows"] != 5041 or output["candidate_rows"] != 50410:
        raise AssertionError("Unexpected public dataset evaluation size")
    return output


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--check-fresh", action="store_true")
    a = p.parse_args()
    print(json.dumps(validate(a.root, check_fresh=a.check_fresh), indent=2))


if __name__ == "__main__":
    main()
