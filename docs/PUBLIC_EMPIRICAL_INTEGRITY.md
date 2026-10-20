# Recompute scan-level reliability using the public empirical data

The public repository includes four measured empirical units, **U01–U03** (UJIIndoorLoc, 3 buildings) and **U09** (Hong Kong), plus source code for the original scan-level reliability computation and SQS. The demonstration below uses the same `wifi_integrity.reliability.indicators._unit_features` and `reconstruct_sqs` implementations as the existing research source; it does not replace them with new algorithms.

## One command from measured input to native output

From the repository root:

```bash
python -m pip install -e ".[dev,empirical]"
python scripts/reproduce_public_integrity.py
```

To run only HK U09 (also exercised by GitHub Actions):

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/reproduce_public_integrity.py --units U09
python scripts/check_public_integrity_release.py --check-fresh
```

The script reads `data/empirical/U01.csv.gz`, `U02.csv.gz` and `U03.csv.gz`; for **U09**, it reads the original-order `data/radio_maps/hk_u09_train.csv.gz` and `data/empirical/hk_u09_test_ordered.csv.gz`, not the separately shuffled HK demonstration table. It validates the expected original study counts and retained scan IDs, and calls the **existing original** reliability implementation without retraining estimators.

Outputs are written under the locally ignored `results/public_integrity/` directory:

- `Uxx_scan_reliability.csv.gz`: per-query diagnostic indicators, three composites (SQS, C_sigma, FII), diagnostic coordinates, relative ground-truth coordinates and scan identifiers.
- `Uxx_retrieved_candidates.csv.gz`: ten nearest diagnostic radio-map candidates for each test scan, using local relative metric coordinates.
- `summary.json`: number of processed records, average/median SQS and source file hashes.

Frozen examples of these **freshly computed** outputs are committed to `examples/empirical_integrity/` so that users can inspect the results without rerunning the algorithm.

## Verification against committed outputs

```bash
python scripts/check_public_integrity_release.py
```

This checks all 5,041 stored scan-feature rows and 50,410 candidate rows, scan key alignment, rank completeness and exact SQS reconstruction. The optional `--check-fresh` matches all 831 U09 scan IDs and compares mean and median SQS with a tolerance of 0.001 on the unit interval. It **reports** the maximum and mean absolute per-scan differences instead of claiming bit-for-bit identity across different NumPy/BLAS environments. The source implementation's float32 nearest-candidate selection can differ at near-ties even with single-thread execution. Original historical outputs remain unchanged.

| Unit | Training RSS scans | Test scans | Candidate rows |
|---|---:|---:|---:|
| U01 | 4,628 | 1,157 | 11,570 |
| U02 | 4,402 | 1,101 | 11,010 |
| U03 | 7,808 | 1,952 | 19,520 |
| U09 | 3,319 | 831 | 8,310 |
| **Total** | **20,157** | **5,041** | **50,410** |

**Distinguish three kinds of output.** (1) These files are *new native computations* from the released measurements. (2) `results/empirical/hk_u09/historical_*.csv.gz` contain the **stored original** eight-estimator and scan-level results. (3) `results/approved/` contains approved original **ten-unit aggregate summaries**. The new computations are not guaranteed to equal the archived historical outputs because candidate tie handling, source ordering, numerical environment and preprocessing may differ. No historical output has been overwritten.

SQS uses cohort-relative scaling in the current implementation. This retrospective execution is **not** an independently calibrated online reliability guarantee, and the command does not retrain all eight historical models or measure prospective gross-error-warning performance.

For the remaining six dataset units, consult [official dataset downloads and the required local input format](DATASET_DOWNLOADS_AND_FORMAT.md). To reproduce an exact study experiment, retain its original split and preprocessing decisions.
