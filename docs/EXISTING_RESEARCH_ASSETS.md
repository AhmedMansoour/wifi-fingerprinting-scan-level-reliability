# Existing measured inputs, radio map and historical results

The repository already contains the original Python indicator, SQS, estimator,
analysis and Android application source. This addition does **not** invent or
re-run the historical experiments. It supplies their existing HK U09 inputs and
approved outputs in a consistent, origin-free coordinate frame.

## Where to find the files

- `data/empirical/hk_u09_ap_relative.csv.gz`: previously published measured U09 input (3,319 train; 831 test). Its rows were shuffled on release and reidentified, so do not join by its public `HK_SCAN_*` identifiers.
- `data/radio_maps/hk_u09_train.csv.gz`: the **same 3,319 training measurements**, preserved in source order, with AP1...AP525 and relative coordinates. This is the fingerprint radio map, **not** a floor-plan image.
- `data/empirical/hk_u09_test_ordered.csv.gz`: the same 831 test measurements in original evaluation order, with `U09-test-000000` through `U09-test-000830`. It makes joining the preexisting results unambiguous.
- `results/empirical/hk_u09/historical_estimator_predictions.csv.gz`: 6,648 saved original predictions, 8 estimators × 831 queries, not baseline retraining.
- `results/empirical/hk_u09/historical_scan_reliability.csv.gz`: 831 original indicator and SQS records.
- `results/empirical/hk_u09/historical_reliability_decisions.csv.gz`: 6,648 original per-estimator reliability and gross-error decision records.
- `results/approved/`: original approved experimental **aggregate summaries** for the ten-unit study, including SQS ablations, association/CI, gross-error results, floor-aware validation, warning sensitivity and runtime. These are stored outputs, not rerun experiments.

A single fixed local-origin translation has been applied consistently. The original coordinate origin is not distributed. This translation preserves pairwise distances and horizontal positioning errors. Original per-estimator coordinate rounding differs by up to 0.03 m for some methods. These historical values are deliberately preserved rather than forcibly replaced with more precise input coordinates.

## Verify original outputs

```bash
python scripts/verify_existing_research_assets.py
```

This performs bytewise checksums, dataset count/identity checks, cross-file scan-index matching and coordinate/error invariance checks. It **does not** claim to retrain all eight historical estimators or regenerate the original indicators from scratch.

To recompute a separate new KNN/WKNN/Random Forest baseline from measured U09 data:

```bash
python -m pip install -e ".[dev,empirical]"
python scripts/reproduce_release.py --mode hk-u09
```

The original ten-unit input archive also contains nine other relative-coordinate measured units, but their source-specific third-party redistribution permissions are recorded as pending. Those nine datasets are intentionally absent from this GitHub commit pending documented data rights, while aggregate evaluation outputs are supplied. Original floor-plan images and map vectors are never supplied.
