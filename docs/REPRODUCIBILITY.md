# Reproducibility and evidence limits

Three distinct execution routes must not be conflated:

1. **Public synthetic demonstration:** `python scripts/reproduce_release.py --mode demo`; `python scripts/validate_synthetic_combined.py`. These test packaging, I/O, estimator invocation and synthetic source-to-output operations only.
2. **Private empirical reference replay:** `python scripts/reproduce_release.py --mode reference`; this **requires separately authorized** `reference/approved/legacy_canonical/` records, intentionally absent from the public archive. Reference replay recomputes output statistics from historical features/predictions, not model retraining.
3. **Native empirical pipeline:** requires the original study datasets and precise split/protocol controls. These data and complete historical run artifacts are not distributed here. A run on the synthetic fixture cannot reproduce reported study positioning accuracy or warnings.

`tests/unit/` run in the public checkout. `tests/reference/` need generated products or separately supplied research assets. The default pytest configuration runs only public-safe unit tests; the reference suite is not claimed to pass without those inputs.

Historical timing: the 99-run Android result concerns post-retrieval indicator/composite/warning computation, excluding scan capture and positioning stages. Cohort-relative adverse percentile thresholds do not establish prospective warning calibration; deployable cutoffs need a separate fixed calibration cohort and independent evaluation. Cross-dataset robustness is limited to the evaluated dataset units and estimators.
