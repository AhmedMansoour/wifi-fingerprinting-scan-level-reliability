# Obtaining and formatting the ten empirical evaluation units

This guide is for executing the **existing** Wi-Fi fingerprinting estimators, scan-level reliability code, and research analysis. The public repository contains measured UJIIndoorLoc units U01–U03 and measured HK U09. For U04–U08 and U10, use the dataset publishers' download pages below and prepare the input locally. The publisher datasets have their **own** licenses and attribution requirements; their files are not relicensed under this repository's MIT code license.

## 1. Unit registry and original download pages

| Unit | Study unit | Original dataset / official download | Public data in this repository | Manuscript split (train/test) |
|---|---|---|---|---:|
| U01 | UJI Building 0 | [UJIIndoorLoc, UCI](https://archive.ics.uci.edu/dataset/310/ujiindoorloc), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | `data/empirical/U01.csv.gz` | 4,628 / 1,157 |
| U02 | UJI Building 1 | [UJIIndoorLoc, UCI](https://archive.ics.uci.edu/dataset/310/ujiindoorloc), CC BY 4.0 | `data/empirical/U02.csv.gz` | 4,402 / 1,101 |
| U03 | UJI Building 2 | [UJIIndoorLoc, UCI](https://archive.ics.uci.edu/dataset/310/ujiindoorloc), CC BY 4.0 | `data/empirical/U03.csv.gz` | 7,808 / 1,952 |
| U04 | TUT WLAN | [WLAN (WiFi) RSS database, Zenodo 1161525](https://zenodo.org/records/1161525) | **Download from publisher** | 1,142 / 286 |
| U05 | TAU Building 01 | [Additional TAU datasets, Zenodo 3819917](https://zenodo.org/records/3819917), `Database_Building01` | **Download from publisher** | 8,309 / 2,076 |
| U06 | TAU Building 02 | [Additional TAU datasets, Zenodo 3819917](https://zenodo.org/records/3819917), `Database_Building02` | **Download from publisher** | 7,433 / 1,858 |
| U07 | Tampere SAH1 | [Tampere multi-building Wi-Fi RSS, Zenodo 5174851](https://zenodo.org/records/5174851), `SAH1` | **Download from publisher** | 7,558 / 1,889 |
| U08 | Tampere TIE1 | [Tampere multi-building Wi-Fi RSS, Zenodo 5174851](https://zenodo.org/records/5174851), `TIE1` | **Download from publisher** | 8,547 / 2,136 |
| U09 | HK Block Z | Study-derived observations, anonymous APs and local relative coordinates | `data/radio_maps/hk_u09_train.csv.gz`, `data/empirical/hk_u09_test_ordered.csv.gz`; combined anonymous input at `data/empirical/hk_u09_ap_relative.csv.gz` | 3,319 / 831 |
| U10 | DSI | [DSI Wi-Fi fingerprinting dataset, Zenodo 3778646](https://zenodo.org/records/3778646) | **Download from publisher** | 1,374 / 343 |

These links point to **original authoritative data records**, not necessarily downloadable replicas of the exact ESWA harmonized unit files. The research uses its own preprocessing and train/test partitions. A user's new partition from the same published source should not be presented as the identical paper experiment.

## 2. Required canonical file format

Save each separately authorized unit as `LOCAL_MEASURED_UNITS/U04.csv.gz` (replace `U04` with its unit ID). The file must be a gzip-compressed UTF-8 CSV with exactly these eight columns **in this order**:

```csv
dataset,group,split,row_id,floor,x,y,rss_json
```

Example *fabricated* rows for unit U04:

```csv
dataset,group,split,row_id,floor,x,y,rss_json
TUT_WLAN_RSS_1161525,TUT,train,U04-train-000000,0,12.50,7.00,"{""AP1"":-63.0,""AP4"":-80.0}"
TUT_WLAN_RSS_1161525,TUT,test,U04-test-000000,0,13.00,8.25,"{""AP1"":-66.0,""AP4"":-78.0}"
```

Rules:

1. `dataset` and `group` must match the corresponding strings in `config/datasets.yaml`. For U09, the existing public `HK_U09` / `HK_LOCAL` aliases are also accepted by the input stager.
2. `split` must be `train` (radio-map fingerprints with reference locations) or `test` (held-out scans with ground-truth locations for retrospective scoring). Preserve the study-specific assignments when seeking manuscript equivalence.
3. `row_id` must be unique within a unit; identifiers must not expose source participants or hardware IDs. Preserve test-row ordering when aligning existing paper predictions.
4. `floor` is a **categorical integer**, such as 0, 1, 2. Do not treat it as a floor height. If source floors are unavailable (U10), use `-1` consistently.
5. `x`, `y` are finite **local metric positions**, in metres, with the same origin, scale and axes across training and test rows of that unit. Translating all positions by one common offset changes no 2D error or distance; do not independently shift train and test sets. Keep each unit's coordinate frame separate.
6. `rss_json` is an escaped JSON object of AP labels to **observed RSSI in dBm**. Use `AP1`, `AP2`, ... consistently across all scans *within the same unit*. If a signal is unobserved, omit that AP; do not place `100` or `0` as a fake measurement. The source-specific +100 missing sentinel should be removed. Do not mix units' AP namespaces or publish real MAC addresses, SSIDs or router names.
7. A `.csv.gz` may be read with `pandas.read_csv` or Python `gzip.open`. No floor-plan image, building vector, geodetic coordinate origin, inverse AP-to-BSSID mapping, or real SSID is necessary.

### Unit metadata mapping

| Unit(s) | `dataset` | `group` |
|---|---|---|
| U01 | `UJIndoorLoc` | `Building0` |
| U02 | `UJIndoorLoc` | `Building1` |
| U03 | `UJIndoorLoc` | `Building2` |
| U04 | `TUT_WLAN_RSS_1161525` | `TUT` |
| U05 | `TAU_ADDITIONAL_3819917` | `Database_Building01` |
| U06 | `TAU_ADDITIONAL_3819917` | `Database_Building02` |
| U07 | `TAMPERE_MULTIBUILDING_5174851` | `SAH1` |
| U08 | `TAMPERE_MULTIBUILDING_5174851` | `TIE1` |
| U09 | `BlockZ-10W-1719W` *(or the published `HK_U09`)* | `BlockZPolyU` *(or the published `HK_LOCAL`)* |
| U10 | `DSI_3778646` | `single_area` |

## 3. Transforming original publisher files

Download and extract the indicated source into an **external local folder**. Prepare one source unit at a time, using the publisher's own measurement/coordinate files:

- **UJIIndoorLoc, U01–U03:** The original files contain `WAP001`–`WAP520`, `LONGITUDE`, `LATITUDE`, `FLOOR`, `BUILDINGID`. Group building IDs 0, 1 and 2 separately. The UCI `trainingData.csv` and `validationData.csv` provide an official split, **not** the independent ESWA 80/20 study split. The already released U01–U03 files supply the study-derived partitions.
- **TUT WLAN, U04:** Pair each `Training_rss.csv` row to the same row in `Training_coordinates.csv`; repeat for the corresponding `Test_*.csv` files. The source provides 3D location data and uses `100` as an unobserved-signal marker. The ESWA count is not the same as the original publisher split.
- **TAU U05–U06:** In each building folder, pair `rm_rss.csv` with `rm_crd.csv` by **row number** for the radio map; pair the equivalent `eval_*` files for queries. Both have metric XY positions and floor IDs. Missing RSS values use `+100` in the original.
- **Tampere U07–U08:** In each of `SAH1` and `TIE1`, match `*_training_rss.csv` and `*_training_coordinates.csv` by row, likewise `*_test_*` files. The publisher's tests have different sizes from the manuscript's derived splits; preserve the study splits if exact comparison is required.
- **DSI U10:** Read the source radio-map and evaluation files from the Zenodo archive; inspect the original columns and measurement convention before selecting XY, APs and any floor code. In the ESWA registry, U10 has no floor ground truth: set `floor=-1`. Keep the publisher observations and document your split.

For both a simple wide RSS table and the publisher's paired RSS/coordinates files, use `scripts/import_external_unit.py` (usage below). It converts columns to a single stable AP namespace and writes the eight-column format; it does **not** reproduce an unpublished study-specific split. If source RSS and coordinates are in separate files, inspect and set `--floor-index` correctly for the particular archive.

```bash
# Example: original TUT train/test RSS and coordinate files (choose the
# actual floor column index by examining the downloaded CSV files).
python scripts/import_external_unit.py --unit U04 --mode paired \
  --train-rss /datasets/TUT/Training_rss.csv \
  --train-coords /datasets/TUT/Training_coordinates.csv \
  --test-rss /datasets/TUT/Test_rss.csv \
  --test-coords /datasets/TUT/Test_coordinates.csv \
  --floor-index 2 --output-dir LOCAL_MEASURED_UNITS

# Example: official wide UJI sources, building 0 (not the paper split).
python scripts/import_external_unit.py --unit U01 --mode wide \
  --train /datasets/UJI/trainingData.csv --test /datasets/UJI/validationData.csv \
  --x-column LONGITUDE --y-column LATITUDE --floor-column FLOOR \
  --building-column BUILDINGID --building-value 0 --ap-prefix WAP \
  --output-dir LOCAL_MEASURED_UNITS
```

The converter does not rescale RSS or positions, estimate missing floor labels, infer unknown file headers, or determine a manuscript's held-out scans. Select the correct columns based on each original dataset's documentation.

## 4. Preparing matrices and executing code

```bash
python -m pip install -e ".[dev,empirical]"
python scripts/validate_uji_release.py
# Prepare the publicly included UJI study units:
python scripts/stage_existing_units.py --input-dir data/empirical --units U01 U02 U03
# Prepare an externally downloaded/transformed unit while accepting an
# independently chosen split different from the paper:
python scripts/stage_existing_units.py --input-dir LOCAL_MEASURED_UNITS --units U04 --allow-custom-splits
# For an exact study-derived unit, omit --allow-custom-splits:
python scripts/stage_existing_units.py --input-dir LOCAL_MEASURED_UNITS --units U04
```

This produces `data/processed/units/U04/radio_map_matrices.npz`, `ap_vocabulary_train.json`, and `scan_metadata.csv.gz` using the **existing original** harmonization functions. The corresponding existing estimator code can then be invoked (example):

```bash
python -m wifi_integrity benchmark-native --units U04 --estimators knn,wknn --output-name u04_native.csv.gz
```

Historical experimental outputs in `results/approved/` and `results/empirical/hk_u09/` are archived results and are **not** overwritten by this pipeline. For reproducible comparisons, keep source download/version, choices of columns, transformations, split membership, AP mapping, software versions and random seeds.

## 5. Data rights and scientific reproducibility

UJIIndoorLoc's **CC BY 4.0** explicitly allows redistribution with credit. For the other publishers, their source records are linked above; publicly available files do **not** by themselves establish that this repository may rehost modified copies. Readers should download directly and follow each publisher's terms. Different source versions, user-defined splits or preprocessing may produce different numbers from the ESWA reference results.
