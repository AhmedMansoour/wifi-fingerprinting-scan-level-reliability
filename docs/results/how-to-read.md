# How to read one scan-level result

The main public empirical output contains **one row per held-out Wi-Fi scan**. It describes the observed signals, match support, candidate geometry and composite diagnostic scores. The accompanying candidate table lets you inspect the ten reference fingerprints retrieved for that query.

## Three files to know

| Name | Source | How to interpret it |
|---|---|---|
| `Uxx_scan_reliability.csv.gz` | Fresh indicator computation | One row per scan; individual indicators and `SQS`, `C_sigma`, `FII` |
| `Uxx_retrieved_candidates.csv.gz` | Diagnostic candidate retrieval | Ten ranked candidate reference positions per scan |
| `summary.json` | Verification metadata | Counts, mean/median SQS, and source-input checksums |

The freshly calculated files are written to `results/public_integrity/`. Examples of the same output types are checked into [`examples/empirical_integrity/`](https://github.com/AhmedMansoour/wifi-fingerprinting-scan-level-reliability/tree/main/examples/empirical_integrity).

## Questions to ask for each scan

**1. What did the device see?** Start with AP count and RSS statistics. A query with fewer visible APs may have weaker fingerprint support, but no single indicator decides reliability on its own.

**2. How well did the query match the radio map?** Inspect RSS distance, cosine similarity, overlap and AP-set novelty. A strong signal match does not guarantee that candidate locations are spatially close.

**3. Do retrieved reference points agree spatially?** Inspect candidate spread (`sigma_fps`), candidate-set diameter (`D_cand`) and neighborhood instability (`I_k`). These tell different stories from RSS match alone.

**4. Is there good local reference support?** Examine the local reference-point density and nearest-reference distances.

**5. What does the composite summarize?** SQS uses five components: signal match, candidate geometry, AP count, overlap and density. It uses cohort-relative scaling and is **not a probability of correct positioning**.

[See the full 18-indicator reference](../INDICATORS.md) for exact output column names and adverse directions.

## Scan and candidate rows align by ID

The `row_id` field identifies the scan in the scan-level file and associates it with the candidate rows. For each scan, the public integrity example stores exactly **10** candidate ranks. Across four units, this yields **5,041 scan rows** and **50,410 candidate rows**.

!!! info "Three different concepts"
    - **Positioning error (metres):** requires a position prediction and a ground-truth reference.
    - **SQS:** reports normalized scan/radio-map support, not error in metres.
    - **Gross-error warning:** a rule that must define its threshold and reference/calibration cohort. It is not automatically produced as an independently validated future alarm by the public scan-feature command.

## What to inspect first, without running Python

The [four-unit public computation summary](https://github.com/AhmedMansoour/wifi-fingerprinting-scan-level-reliability/blob/main/examples/empirical_integrity/summary.json) records:

| Unit | Test scans | Diagnostic candidate rows |
|---|---:|---:|
| U01 | 1,157 | 11,570 |
| U02 | 1,101 | 11,010 |
| U03 | 1,952 | 19,520 |
| U09 | 831 | 8,310 |
| **Total** | **5,041** | **50,410** |

**Next:** [Understand the original study outputs](evidence.md) · [Run the computation](../start/quickstart.md).
