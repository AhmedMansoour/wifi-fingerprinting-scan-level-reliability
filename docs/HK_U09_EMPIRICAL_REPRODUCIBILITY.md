# Empirical HK U09: executable 2D positioning baseline

The published input `data/empirical/hk_u09_ap_relative.csv.gz` contains 4,150 **real observed** HK Wi-Fi scans. It is not the ten-unit synthetic demonstration. Real BSSIDs and original scan identifiers are replaced with opaque AP labels and release scan IDs; coordinates are in local metres with no absolute origin. RSS observations and the existing 3,319/831 training/query split are preserved.

## One-command reproduction

At the repository root after `python -m pip install -e ".[dev]"`:

```bash
python scripts/reproduce_release.py --mode hk-u09
# Or run the native estimator driver directly:
python scripts/evaluate_hk_u09.py --check-frozen
# To save per-scan predictions locally (not tracked by Git):
python scripts/evaluate_hk_u09.py --save-predictions
```

Outputs: `results/empirical/hk_u09/summary.json`; optional `predictions.csv.gz`. `--check-frozen` compares specified output summaries with `docs/hk_u09_expected_summary.json`, with an absolute 0.03 m numerical tolerance for possible dependency changes. CI reruns the baseline and checks the input SHA-256.

## Explicit protocol

- Models: existing repository `RetrievalEstimator` for KNN and WKNN, and `make_random_forest` for RF. No additional independent estimator source is used.
- KNN and WKNN: k=5, Euclidean distance on the existing legacy feature interface (`0` for unobserved APs). WKNN uses power=2. RF: 80 trees, maximum depth 18, minimum leaf 2, `max_features=sqrt`; seed=42.
- AP vocabulary learned exclusively from *training* RSS. Train=3,319, test=831, features=525. No test labels are used in training, feature selection, or estimator settings. No hyperparameter tuning was done on the held-out test set.
- All models are floor-agnostic and return only (x,y). True floors are not available to the estimators; wrong-floor detection and 3D positioning are **not evaluated**. Error is Euclidean 2D distance in relative metres.
- Input checksum: `b99bac3454e8f0f306c7fb8c012a7def5e277251c8013304e50e02ae51717078`.

## Independently executed results on the released U09 table

| Estimator | Mean error (m) | Median (m) | P90 (m) | P95 (m) | RMSE (m) |
|---|---:|---:|---:|---:|---:|
| KNN | 4.3766 | 3.4504 | 9.1161 | 10.6208 | 5.7524 |
| WKNN | 4.1537 | 3.2395 | 8.6327 | 10.2415 | 5.4854 |
| Random Forest | 6.3518 | 5.0559 | 11.9108 | 16.1534 | 8.3550 |

This is a **new reproducible empirical baseline** and not a reconstruction of the paper's original tuning or eight-estimator evaluation; it does not establish equivalence with published results. The 831 query scans should not be treated as 831 statistically independent trajectory trials because observations may be spatially correlated. No inference about calibration, gross-error warning validity, or cross-dataset performance follows from these numbers. The other nine empirical units and the original reference outputs remain outside this public evaluation.
