# Test scopes

Run `python -m pytest -q` from the repository root for the default unit suite. It covers configuration, harmonization, estimator contracts, demo entry points, SQS arithmetic, empty Android schema, frozen calibration, and public HK export invariants.

`python scripts/check_native_estimators.py --require-all` additionally exercises all eight native fit/predict adapters on synthetic inputs and requires all optional frameworks.

The tests under `tests/reference` retain historical complete-workspace assumptions. They are not included in the default suite. Public reproducibility is checked through `scripts/reproduce_release.py --mode reference` and `scripts/reproduce_uncertainty.py`; consult [VALIDATION.md](../VALIDATION.md) for the actual outcomes and scope.
