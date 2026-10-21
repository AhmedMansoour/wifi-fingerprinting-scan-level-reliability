# Quick start: measured Wi-Fi input to indicator results

This route runs the **existing research source code** on four real-data units included in GitHub: U01–U03 from UJIIndoorLoc and the relative-coordinate HK U09 subset.

!!! tip "No access-point hardware required"
    You only need Python and the released data files to reproduce this offline evaluation. The Android app and a live phone scan are not required.

## Before you start

- Python 3.10 or newer, recommended 3.11 or 3.12.
- Git and a command-line terminal.
- The package dependencies in `pyproject.toml`.

## 1. Download the repository

```bash
git clone https://github.com/AhmedMansoour/wifi-fingerprinting-scan-level-reliability.git
cd wifi-fingerprinting-scan-level-reliability
```

## 2. Install the research environment

```bash
python -m pip install -e ".[dev,empirical]"
```

The `empirical` option pins the numerical libraries used for the published held-out HK baseline checks.

## 3. Compute scan-level reliability from measured data

```bash
python scripts/reproduce_public_integrity.py
```

This runs the original reliability code on 20,157 training and 5,041 query scans. It writes new files under the ignored `results/public_integrity/` folder; it does **not** modify the archived study outputs.

## 4. Inspect and check the outputs

```bash
python scripts/check_public_integrity_release.py
```

The checker validates scan IDs, row counts, ten retrieved candidate ranks per query and exact SQS arithmetic in the stored public examples.

| File | What you will see |
|---|---|
| `results/public_integrity/U09_scan_reliability.csv.gz` | One scan's indicator values and composite outputs per row |
| `results/public_integrity/U09_retrieved_candidates.csv.gz` | Ten ranked candidate reference points per scan |
| `results/public_integrity/summary.json` | Rows processed, SQS summaries and source file hashes |

## Shorter run: HK U09 only

```bash
python scripts/reproduce_public_integrity.py --units U09
```

To compare this fresh U09 run with the committed example, run:

```bash
python scripts/check_public_integrity_release.py --check-fresh
```

The comparison checks the same 831 scan identities and aggregate mean/median SQS within a documented 0.001 tolerance; it reports per-scan numerical differences due to candidate near-ties.

## Also try a positioning estimator

```bash
python scripts/reproduce_release.py --mode hk-u09
```

That separate baseline trains KNN, WKNN and Random Forest and evaluates them against held-out 2D positions. It is **not** the original full eight-estimator historical reproduction.

## If something goes wrong

| Problem | First check |
|---|---|
| Missing `wifi_integrity` package | Run the editable installation from the repository root |
| Missing `.csv.gz` inputs | Confirm `data/empirical/` and `data/radio_maps/` were cloned |
| Different run summaries | Compare Python/dependency versions and numerical backend, then use the documented aggregate tolerance |
| Looking for U04–U08 or U10 | See the [official download and conversion guide](../DATASET_DOWNLOADS_AND_FORMAT.md) |

**Next:** [Understand the CSV outputs](../results/how-to-read.md) · [See exact reproducibility boundaries](../results/evidence.md).
