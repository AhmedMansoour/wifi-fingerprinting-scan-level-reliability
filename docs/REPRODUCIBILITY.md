# Reproducibility and evidence limits

Four distinct execution routes must not be conflated:

1. **Public synthetic demonstration:** `python scripts/reproduce_release.py --mode demo`; `python scripts/validate_synthetic_combined.py`. These test packaging, I/O, estimator invocation and synthetic source-to-output operations only.
2. **Public empirical HK U09 baseline:** `python scripts/reproduce_release.py --mode hk-u09` trains the existing KNN, WKNN and Random Forest implementations on 3,319 observed training scans, then evaluates 831 held-out scans. See `docs/HK_U09_EMPIRICAL_REPRODUCIBILITY.md`. This is a new baseline, not the historical eight-estimator study replay.
3. **Private empirical reference replay:** `python scripts/reproduce_release.py --mode reference`; this **requires separately authorized** `reference/approved/legacy_canonical/` records, intentionally absent from the public archive. Reference replay recomputes output statistics from historical features/predictions, not model retraining.
4. **Full native empirical pipeline:** requires the original study datasets and precise split/protocol controls. These data and complete historical run artifacts are not distributed here. A run on the synthetic fixture cannot reproduce reported study positioning accuracy or warnings.

`tests/unit/` run in the public checkout. `tests/reference/` need generated products or separately supplied research assets. The default pytest configuration runs only public-safe unit tests; the reference suite is not claimed to pass without those inputs.

Historical timing: the 99-run Android result concerns post-retrieval indicator/composite/warning computation, excluding scan capture and positioning stages. Cohort-relative adverse percentile thresholds do not establish prospective warning calibration; deployable cutoffs need a separate fixed calibration cohort and independent evaluation. Cross-dataset robustness is limited to the evaluated dataset units and estimators.

## External measured dataset inputs

See [dataset download links and canonical input format](DATASET_DOWNLOADS_AND_FORMAT.md). `scripts/import_external_unit.py` adapts wide or paired Wi-Fi RSS files, and `scripts/stage_existing_units.py` prepares radio-map matrices with the original repository code. New partitions should not be equated with the study's archived numerical results.

## Fresh empirical scan-level reliability outputs on public units

The original indicator and SQS implementations can now be executed directly using measured UJIIndoorLoc U01–U03 and anonymous HK U09 RSS tables: `python scripts/reproduce_public_integrity.py`. The frozen new results (5,041 scan records and 50,410 candidate records) are under `examples/empirical_integrity/`. Execute `python scripts/check_public_integrity_release.py` to validate their row identities and arithmetic. These results are not a replacement for the original paper's eight-estimator retrospective tables. See `docs/PUBLIC_EMPIRICAL_INTEGRITY.md`.
