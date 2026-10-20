# Wi-Fi Fingerprinting Scan-Level Integrity

**Research implementation accompanying a manuscript under review in Expert Systems with Applications.** This repository distributes original source, synthetic demonstration inputs, and a distinct empirical HK U09 data file under the MIT license. See `LICENSE` and `THIRD_PARTY_NOTICES.md`.

The Python package implements Wi-Fi fingerprinting estimators and diagnostic/reliability components. The Android Java application inspects scans using an imported, authorized local radio map. The project contains a deterministic **fully synthetic** ten-unit input fixture for exercising source code and data preparation, not the observations used in the study. HK U09 real RSS scans with AP1–AP525 tokens and origin-free local metric positions are separately published under `data/empirical/`. No original HK floor-map images/vectors, original BSSIDs, SSIDs, router names, or geodetic origins are included.

## Installation and tests

Run at the repository root (Python 3.10+, recommended 3.11/3.12):

```bash
python -m pip install -e ".[dev]"
python scripts/assemble_synthetic_combined.py
python -m pytest -q
python scripts/reproduce_release.py --mode demo
python scripts/check_public_release.py
python scripts/validate_hk_empirical.py
```

**These commands are public-fixture tests**, not validation of the paper's empirical results. The combined CSV is deterministically reconstructed from the 10 committed synthetic unit files, with SHA-256 verification. The sample includes 54,520 fabricated training and 13,629 fabricated test scans across ten registry slots, generated from code rather than site measurements. Counts are for interface compatibility only.

```bash
python scripts/validate_synthetic_combined.py
python scripts/prepare_research_workspace.py --combined examples/synthetic_combined/combined_all_datasets.csv.gz
```

The second command constructs a local, ignored analysis workspace from synthetic values; it does not retrain or reconstruct historical paper results.

## Android Studio

Open `android/` in Android Studio; SDK 35, JDK 17 (or compatible Android Gradle tooling) and network access to resolve Android dependencies are required. Run `./gradlew testDebugUnitTest assembleDebug` inside `android/`. The app initializes an empty local database from `android/app/src/main/assets/database/schema.sql` and requires importing your authorized local radio map. **No populated database or original HK building data is distributed.** Java-only smoke tests can run without an Android SDK; see `android/README.md`.

## Limits and research-data access

The real investigation covered ten data units, eight estimators, and 18 selected diagnostic quantities. HK U09 empirical observations (4,150 scans: 3,319 train, 831 test; 525 relabeled APs; 11 levels) are included at `data/empirical/hk_u09_ap_relative.csv.gz`. The remaining nine empirical unit inputs and historical 109,032 estimator reference predictions are not included. `python scripts/reproduce_release.py --mode reference` stops with a clear error unless approved reference records are supplied. Stored-reference replay is not equivalent to independently retraining all eight original estimators. Historical SQS native reconstruction remains under independent verification.

The retrospective, cohort-relative warning scores must not be presented as independently calibrated future-deployment probabilities. The 99-run Android benchmark measures **post-retrieval indicator/composite/warning computation**, not complete end-to-end positioning time. Evidence on robustness is limited to the evaluated conditions, not unseen buildings or arbitrary devices.

See `docs/REPRODUCIBILITY.md`, `docs/CALIBRATION.md`, `docs/WARNING_CALIBRATION.md`, `docs/ANDROID_TIMING.md`, `docs/DATA_AND_PRIVACY.md`, and `PUBLICATION_APPROVAL_REQUIRED.md`.

**Repository organization:** `src/` (Python), `scripts/` (entrypoints), `android/` (Java/Gradle), `config/`, `examples/synthetic_combined/`, `dashboard/`, `web/`, `tests/unit/`, and `docs/`. The `tests/reference/` tests deliberately require separately supplied research assets and are excluded from the default test suite.

## License

Original project source and synthetic fixtures: MIT (see `LICENSE`). The empirical HK table is separately sourced research data, not automatically covered by the software MIT license. Third-party components have their own licenses (see `THIRD_PARTY_NOTICES.md`). Redistribution of empirical radio-map data is not licensed by this repository.
