"""Run the data-free demo or replay separately supplied reference predictions.

The legacy mode name 'published' means manuscript-reference replay. It does not
describe the publication status of the paper or retrain the reference estimators.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
REFERENCE_INPUTS = (
    "reference/approved/legacy_canonical/estimator_predictions_approved.csv.gz",
    "reference/approved/legacy_canonical/estimator_error_summary.csv",
    "reference/approved/legacy_canonical/reliability_features_approved.csv.gz",
    "reference/public/scan_index.csv.gz",
)


def missing_reference_inputs(root: Path) -> list[str]:
    return [name for name in REFERENCE_INPUTS if not (root / name).is_file()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["demo", "reference", "published", "hk-u09"], default="demo")
    parser.add_argument("--check-only", action="store_true", help="Check required inputs without writing outputs")
    args = parser.parse_args()
    if args.mode == "demo":
        if args.check_only:
            print("The demo generates synthetic inputs locally; no research datasets are required.")
            return
        subprocess.run([sys.executable, str(ROOT / "scripts/generate_synthetic_demo.py"),
                        "--output", str(ROOT / "results/demo/synthetic_scans.csv")], check=True)
        subprocess.run([sys.executable, str(ROOT / "scripts/run_synthetic_demo.py"),
                        "--input", str(ROOT / "results/demo/synthetic_scans.csv"),
                        "--output", str(ROOT / "results/demo/demo_results.json")], check=True)
        return
    if args.mode == "hk-u09":
        if args.check_only:
            import hashlib
            path = ROOT / "data/empirical/hk_u09_ap_relative.csv.gz"
            if not path.is_file():
                parser.exit(2, "Missing released HK U09 data file\n")
            from validate_hk_empirical import validate
            print(json.dumps(validate(path), indent=2))
            return
        subprocess.run([sys.executable, str(ROOT / "scripts/evaluate_hk_u09.py"),
                        "--check-frozen"], check=True)
        return
    missing = missing_reference_inputs(ROOT)
    if missing:
        parser.exit(2, "Required public reference inputs are missing.\n"
                    + "\n".join(f"  - {name}" for name in missing)
                    + "\nSee docs/GETTING_STARTED.md. No outputs were generated.\n")
    if args.check_only:
        print("Required reference input files are present; scientific validation has not yet run.")
        return
    from wifi_integrity.benchmark.replay import materialize_published_benchmark
    from wifi_integrity.reliability.sqs import reconstruct_sqs
    import numpy as np
    import pandas as pd
    benchmark = materialize_published_benchmark(ROOT)
    if benchmark["status"] != "passed":
        raise SystemExit("Reference benchmark summary regression failed. Inspect results/logs/.")
    features = pd.read_csv(ROOT / REFERENCE_INPUTS[2])
    delta = np.abs(reconstruct_sqs(features).to_numpy() - features["SQS"].to_numpy())
    if not len(delta) or not np.isfinite(delta).all() or float(delta.max()) >= 1e-12:
        raise SystemExit("Stored-reference SQS reconstruction failed.")
    from wifi_integrity.reliability.analysis import run_reliability_analysis
    (ROOT / 'results/reliability').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / REFERENCE_INPUTS[2], ROOT / 'results/reliability/reliability_features_published.csv.gz')
    analysis = run_reliability_analysis(ROOT)
    if analysis['max_abs_association_median_difference'] >= 1e-9:
        raise SystemExit('Association regression failed')
    actual = pd.read_csv(ROOT / 'results/tables/gross_error_discrimination_summary_native.csv')
    differences = []
    for strategy, filename in [('adaptive_iqr', 'gross_error_adaptive_summary_legacy.csv'), ('fixed_7m', 'gross_error_fixed7m_summary_legacy.csv')]:
        expected = pd.read_csv(ROOT / 'reference/approved/legacy_canonical' / filename)
        merged = actual[actual.strategy == strategy].merge(expected, on='indicator_id', suffixes=('_actual', '_expected'), validate='one_to_one')
        if len(merged) != 18: raise SystemExit('Incomplete discrimination comparison')
        for metric in ['median_auroc', 'median_auprc']:
            difference = np.abs(merged[metric+'_actual'] - merged[metric+'_expected']).to_numpy()
            if not np.isfinite(difference).all() or difference.max() >= 1e-9:
                raise SystemExit('Discrimination regression failed')
            differences.extend(difference)
    report = {'scope': 'stored-reference estimator summaries, SQS arithmetic, association and gross-error discrimination',
              'benchmark': benchmark, 'sqs_rows': len(features), 'sqs_max_abs_difference': float(delta.max()),
              'reliability_analysis': analysis, 'max_discrimination_median_difference': float(max(differences)),
              'native_retraining': False, 'native_indicator_recomputation': False}
    (ROOT / "results/logs/reference_replay.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
