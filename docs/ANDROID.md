# Android implementation

[Home](../README.md) · [Reproducibility](REPRODUCIBILITY.md) · [Availability](ROADMAP.md)

## Wi-Fi Integrity Inspector

The supplied Java v1.0.9 project implements a building-selected, floor-aware inspection workflow. It infers a floor, forms a floor-specific WKNN estimate, retrieves diagnostic candidates, computes the 18 diagnostic quantities, and records the result for inspection and export.

| Interface | Purpose |
| --- | --- |
| Live | Scan, floor inference, position estimate, and diagnostic summary |
| Map | Spatial context, reference points, and candidate geometry |
| Diagnostics | Indicator values, composite scores, and condition-relative warnings |
| History | Previously recorded inspections |
| Radio Maps | Installed map inventory and ZIP import |

The supplied configuration specifies Java 17, Android compile/target SDK 35, and minimum API 26. These are source configuration values; this repository does not yet distribute an APK or claim a fresh Android build.

## Bring a radio map

A building import package contains the following files. The software source will be distributed separately from research radio maps.

| File | Required content |
| --- | --- |
| `manifest.json` | Building name and stable identifier |
| `floors.csv` | Floor identifiers, floor numbers, names, and coordinate bounds |
| `reference_points.csv` | Reference-point identifiers, floor identifiers, and local coordinates |
| `fingerprints.csv` | Reference-point identifier, AP BSSID, and RSS |
| `calibration.csv` | Optional, exact floor/estimator calibration profiles |
| `floorplans/` | Optional map images |

A map must use the AP identifiers observable by the phone and a consistent coordinate system. Without an exact matching calibration profile, raw diagnostics can remain available while calibrated scores and warnings are unavailable. Calibration from another floor or estimator should not silently replace the missing profile.

## Processing and timing

Wi-Fi acquisition, floor inference, map loading, fingerprint preparation, candidate retrieval, coordinate estimation, indicator computation, and persistence are measured as separate stages. Android controls scan cadence, so a sub-millisecond diagnostic computation does not imply a sub-millisecond complete positioning cycle.

The application exports scan summaries, indicator values, stage timings, floor-ranking records, and device metadata. Runtime comparisons should identify the selected building/floor, radio-map and AP dimensions, estimator setting, application version, and device/OS.

## Source-release preparation

A source-only package needs a safe empty-database setup and an import path before positioning can run. The preparation work excludes the bundled research seed database, real AP mappings, floor images, and historical scan exports. Android Gradle synchronization, APK compilation, map import, and live-device operation remain distinct validation steps.
