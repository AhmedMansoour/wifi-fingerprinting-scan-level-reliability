# Reference calibration and held-out evaluation

## What the historical results establish

Historical analyses use cohort-relative indicator scaling and ranks to study associations and gross-error discrimination. When a distribution is derived from the evaluated cohort, its results are retrospective. It must not be described as an independently fitted online calibration or as prospective warning performance.

The Android implementation can apply condition-specific reference distributions. The reported live timing measurements demonstrate the cost of indicator/composite/warning computation. They do not establish the statistical adequacy or independent predictive effectiveness of an imported profile.

## Protocol for prospective use

1. Freeze the radio map, training AP vocabulary, positioning estimator and its settings, and diagnostic candidate count (`M = 10`).
2. Collect a separate calibration cohort representative of the intended condition. Keep the final evaluation cohort separate; account for repeated locations, sessions, and devices when designing the split.
3. Fit the 5th/95th percentile scaling bounds and empirical distributions of the 15 individual indicators on calibration data only.
4. Construct SQS, Cσ, and FII with those frozen bounds. Fit the three composite reference distributions on the resulting calibration scores.
5. Freeze a versioned profile with its cohort identity, floor, estimator, sample counts, and provenance. Apply it unchanged to held-out evaluation scans.
6. Evaluate warning behavior against held-out outcomes. Any recalibration creates a new profile and requires a new evaluation; query observations must not silently alter the existing reference.

The included Python builder checks disjoint scan IDs, explicit profile roles, and condition identity. ID disjointness alone cannot prove session/location independence or representativeness. The minimum of eight finite records is an input guard, not a claim that eight scans are adequate for calibration.

## Adverse percentile and cutoff

For a reference set of size `n`, adverse percentile is:

- High-is-adverse: `count(reference <= observed) / n`.
- Low-is-adverse: `count(reference >= observed) / n`.

Ties are inclusive. A warning is raised at **adverse percentile ≥ 0.80**. Ties can make the actual warning rate differ from 20%. These percentiles express condition-relative extremeness; neither they nor SQS are calibrated probabilities of positioning failure. Missing indicator values must be shown as unavailable.

Composite scaling clips `(value - q05) / (q95 - q05)` to `[0, 1]`. The implementation uses the Android-compatible neutral value `0.5` for a degenerate scaling interval or missing scaling input; this fallback is not evidence of good support.

## Build a frozen profile

Prepare a local CSV containing `scan_id` and the 15 raw indicator columns, plus a separate CSV containing held-out `scan_id` values.

```bash
python scripts/build_calibration.py --input /private/calibration.csv --evaluation-ids /private/heldout_ids.csv --output /private/profiles/site_v1 --floor-id local_floor_1 --estimator WKNN-k3 --reference-id calibration_session_v1 --role calibration
```

Use the exact estimator identity expected by the Android importer. The command writes `profile.json` and `calibration.csv`, refuses to overwrite an existing profile, and records reference-value checksums. Keep both files locally together: the Android CSV alone does not carry all provenance fields.

`--role retrospective` explicitly labels a descriptive cohort profile. The Python online application function rejects retrospective roles and floor/estimator/M mismatches. The Android importer does not enforce the JSON provenance role; deployment owners must preserve and review that provenance themselves. No generic calibration fallback or independent deployment performance is claimed.

Without a matching imported calibration, Android still supports available raw diagnostics. Calibrated composites and warning percentiles remain unavailable. See the [Android import format](../android/IMPORT_FORMAT.md).
