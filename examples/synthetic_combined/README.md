# Fully synthetic ten-unit demonstration data

**These are fabricated software-test observations, not ESWA study measurements.** All scan identifiers, AP tokens, RSS values, level labels and 2D coordinates were generated synthetically. The ten unit names designate compatible input slots, not the actual contents or geometry of the benchmark datasets. No original HK BSSIDs, floor plans, real trajectories or reconstructable site geometry are distributed.

## What's committed to this repository

- `units/U01.csv.gz` through `units/U10.csv.gz`: ten checksum-verified synthetic subsets.
- `validation_summary.json`: recorded SHA-256 digests and expected row counts.
- `README.md`: this explanatory file.

The combined `combined_all_datasets.csv.gz` is **generated locally** rather than stored in the Git repository. From the project root:

```bash
python scripts/assemble_synthetic_combined.py
python scripts/validate_synthetic_combined.py
python scripts/prepare_research_workspace.py \
  --combined examples/synthetic_combined/combined_all_datasets.csv.gz
```

The eight-column CSV schema is:

`dataset,group,split,row_id,floor,x,y,rss_json`

The fixture has 68,149 invented scans (54,520 train / 13,629 test). The x/y coordinates are origin-free, fabricated metre coordinates, and AP identifiers have the `AP_00001` style. These values support installation checks, synthetic unit tests and demonstration execution. **They cannot reproduce the manuscript's empirical accuracy, indicator correlations or warning-state results.** The study-specific data and output records are separately controlled and are not licensed by this synthetic fixture.

For regeneration from the original deterministic generator, consult `scripts/create_public_synthetic_combined.py`; byte-level equivalence also depends on the specified dependencies and compression settings.
