# Run the workflow with your own Wi-Fi data

To process an external dataset, you need **authorized fingerprint measurements, a training radio map, and a held-out query set**. The repository includes a CSV converter and the same harmonization functions used by the research code.

## Canonical eight-column CSV

```csv
dataset,group,split,row_id,floor,x,y,rss_json
```

| Field | Meaning |
|---|---|
| `dataset`, `group` | Unit identifiers consistent with `config/datasets.yaml` |
| `split` | `train` for the radio map, `test` for queries |
| `row_id` | Unique row identifier within the unit |
| `floor` | Categorical integer or `-1` if unavailable |
| `x`, `y` | Local, finite coordinates in metres with a **shared origin and scale** |
| `rss_json` | Observed AP/RSS dictionary such as `{"AP1":-60.0}` |

Omit access points that are not observed rather than inserting invented RSS readings. Do not include original BSSIDs, participant identifiers, SSIDs or site geometry unless you have a clear right and purpose to distribute them.

## Prepare a publisher dataset

1. Download the actual files from the dataset's [publisher page](../DATASET_DOWNLOADS_AND_FORMAT.md).
2. Determine its RSS columns, coordinate columns, floor categories and missing-signal sentinel.
3. Assign stable pseudonymous AP labels within that unit.
4. Keep train/test assignments. A new split is **not** the historical ESWA split.
5. Write a gzip-compressed eight-column CSV (one unit per file).

Use `scripts/import_external_unit.py` to convert wide or paired RSS/coordinate tables. Example CLI options are provided in the [detailed formatting guide](../DATASET_DOWNLOADS_AND_FORMAT.md).

## Build native radio-map matrices

For a prepared U04 file placed under `LOCAL_MEASURED_UNITS/U04.csv.gz`:

```bash
python scripts/stage_existing_units.py \
  --input-dir LOCAL_MEASURED_UNITS --units U04 --allow-custom-splits
```

The script creates processed unit matrices and a training-only AP vocabulary. Once prepared, the existing code can run a supported native positioning baseline:

```bash
python -m wifi_integrity benchmark-native \
  --units U04 --estimators knn,wknn --output-name u04_native.csv.gz
```

!!! warning "Do not claim a paper reproduction after changing the split"
    Reformatting publisher input makes the **code usable** on those measurements. Reproducing the archived paper requires the same source version, split, AP mapping, preprocessing, estimator settings, and evaluation protocol.

**Next:** [See all ten unit sources](../DATASET_DOWNLOADS_AND_FORMAT.md) · [Read the output files](../results/how-to-read.md).
