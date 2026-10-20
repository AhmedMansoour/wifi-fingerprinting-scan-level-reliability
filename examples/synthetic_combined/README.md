# PUBLIC SYNTHETIC combined Wi-Fi data for software demonstrations

## Critical distinction
All 68,149 individual scans, relative 2D positions, RSS readings, AP placements,
and all map-like geometry are **fabricated from a random seed**. These are NOT
measurements from the ESWA study or from the named benchmark datasets. Dataset
and group names are registry slot labels used only for compatibility with the
repository; they DO NOT imply original dataset content is reproduced.

This file is suitable as a PUBLIC **synthetic software-test fixture**. It
CANNOT independently reproduce the paper's empirical accuracy, SQS calibration,
gross-error results, or per-environment conclusions. Do not label it as
"anonymized empirical data" or "processed study data". To reproduce reported
study reference statistics use the separately supplied approved scalar records,
subject to their own permissions.

## Files
- `processing_inputs/combined_all_datasets.csv` is the drop-in eight-column
  table for `scripts/prepare_research_workspace.py --combined ...`.
- `processing_inputs/units/U01.csv.gz` through `U10.csv.gz` are the unit slices.
- `processing_inputs/validation_summary.json` records sizes and SHA-256 hashes.
- `scripts/create_public_synthetic_combined.py` generates all 10 units afresh.

## Data schema
`dataset,group,split,row_id,floor,x,y,rss_json`

Coordinates are fabricated metre-scale local Cartesian positions with no
geodetic origin, genuine reference-point locations, or real floor geometry.
`floor` is a fabricated categorical level, not a true storey label. RSS
observations use fabricated AP keys in the `AP_00001` format, *not HK BSSIDs*.
No real scan rows, raw radio-map signatures, or reversible mappings were used.

## Reproduction
```bash
python scripts/create_public_synthetic_combined.py --output new_public_fixture.zip
unzip new_public_fixture.zip
python scripts/prepare_research_workspace.py \
  --combined processing_inputs/combined_all_datasets.csv
```

The generator is deterministic given its code, seed, and numpy version. A SHA-256
of its committed output is recorded in the included validation summary. The
repository's analysis results are **not** expected to match the original paper
when this fixture is substituted for actual study data.

## Source and permissions
The published release excludes all actual HK indoor geometry, floor-plan
images, vector shapes, Wi-Fi identifiers, and empirically observed positions.
The separately stored 10-unit input ZIP contains real derived data and is
PRIVATE. Redistributing third-party empirical datasets requires dataset-specific
license verification even after IDs and coordinates are transformed.
