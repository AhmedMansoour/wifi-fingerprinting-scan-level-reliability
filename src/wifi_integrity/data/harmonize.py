"""Deterministic harmonization of the frozen combined Wi-Fi fingerprint table."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from wifi_integrity.data.registry import UnitSpec, registry_lookup
from wifi_integrity.hashing import sha256_file, sha256_text

RSS_MISSING_DBM = -110.0
DIAGNOSTIC_MAX_APS = 180

SOURCE_COLUMNS = [
    "dataset",
    "group",
    "building",
    "floor",
    "split",
    "row_id",
    "source_split",
    "source_row",
    "x",
    "y",
    "z",
    "latitude",
    "longitude",
    "coordinate_system",
    "rss_format",
    "rss_json",
    "rss_count",
    "rss_feature_count",
]


def parse_rss_json(value: object) -> dict[str, float]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return {}
    if isinstance(value, dict):
        raw = value
    else:
        try:
            raw = json.loads(str(value))
        except (TypeError, json.JSONDecodeError):
            return {}
    if not isinstance(raw, dict):
        return {}
    parsed: dict[str, float] = {}
    for key, item in raw.items():
        try:
            number = float(item)
        except (TypeError, ValueError):
            continue
        if np.isfinite(number):
            parsed[str(key)] = number
    return parsed


def training_ap_vocabulary(rss_dicts: Iterable[dict[str, float]]) -> list[str]:
    counts: Counter[str] = Counter()
    for rss in rss_dicts:
        counts.update(rss.keys())
    return [ap for ap, _ in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))]


def diagnostic_ap_vocabulary(
    train_rss: Iterable[dict[str, float]],
    test_rss: Iterable[dict[str, float]],
    max_aps: int = DIAGNOSTIC_MAX_APS,
) -> list[str]:
    """Reproduce the approved diagnostic-probe AP ranking.

    Training observations receive weight 2 and held-out-query observations receive
    weight 1, followed by deterministic frequency/name ordering and truncation.
    """
    counts: Counter[str] = Counter()
    for rss in train_rss:
        for ap in rss:
            counts[ap] += 2
    for rss in test_rss:
        for ap in rss:
            counts[ap] += 1
    return [ap for ap, _ in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:max_aps]]


def dense_matrix(
    rss_dicts: list[dict[str, float]],
    vocabulary: list[str],
    fill_value: float = RSS_MISSING_DBM,
) -> tuple[np.ndarray, np.ndarray]:
    index = {ap: column for column, ap in enumerate(vocabulary)}
    values = np.full((len(rss_dicts), len(vocabulary)), fill_value, dtype=np.float32)
    observed = np.zeros((len(rss_dicts), len(vocabulary)), dtype=np.uint8)
    for row, rss in enumerate(rss_dicts):
        for ap, signal in rss.items():
            column = index.get(ap)
            if column is not None:
                values[row, column] = np.float32(signal)
                observed[row, column] = 1
    return values, observed


def _write_table(frame: pd.DataFrame, target_base: Path) -> dict[str, str]:
    """Write Parquet when available and always provide a gzip CSV fallback."""
    outputs: dict[str, str] = {}
    csv_path = target_base.with_suffix(".csv.gz")
    frame.to_csv(csv_path, index=False, compression="gzip")
    outputs["csv_gz"] = str(csv_path)
    try:
        parquet_path = target_base.with_suffix(".parquet")
        frame.to_parquet(parquet_path, index=False)
        outputs["parquet"] = str(parquet_path)
    except (ImportError, ModuleNotFoundError, ValueError):
        pass
    return outputs


def harmonize_combined_table(
    source_csv: str | Path,
    units: list[UnitSpec],
    output_dir: str | Path,
) -> dict[str, object]:
    source_path = Path(source_csv)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    unit_root = output_path / "units"
    unit_root.mkdir(parents=True, exist_ok=True)

    combined = pd.read_csv(
        source_path,
        usecols=lambda column: column in SOURCE_COLUMNS,
        dtype={"row_id": str, "source_split": str},
        low_memory=False,
    )
    lookup = registry_lookup(units)
    pair_index = pd.MultiIndex.from_frame(combined[["dataset", "group"]].astype(str))
    selected_pairs = set(lookup)
    selected_mask = np.fromiter((pair in selected_pairs for pair in pair_index), dtype=bool)
    selected = combined.loc[selected_mask].copy()
    selected["unit_id"] = [lookup[(str(d), str(g))].id for d, g in zip(selected["dataset"], selected["group"])]
    selected["unit_label"] = [lookup[(str(d), str(g))].label for d, g in zip(selected["dataset"], selected["group"])]
    selected["split"] = selected["split"].astype(str).str.lower()
    selected["scan_id"] = selected["unit_id"] + ":" + selected["row_id"].astype(str)
    selected["floor"] = selected["floor"].astype("string")
    selected["x"] = pd.to_numeric(selected["x"], errors="coerce")
    selected["y"] = pd.to_numeric(selected["y"], errors="coerce")
    selected["rss_count"] = pd.to_numeric(selected["rss_count"], errors="coerce").astype("Int64")

    selected = selected.sort_values(["unit_id", "split", "scan_id"], kind="mergesort").reset_index(drop=True)
    canonical_columns = [
        "unit_id", "unit_label", "scan_id", "dataset", "group", "building",
        "floor", "split", "row_id", "source_split", "source_row", "x", "y", "z",
        "latitude", "longitude", "coordinate_system", "rss_format", "rss_json",
        "rss_count", "rss_feature_count",
    ]
    selected = selected[canonical_columns]
    table_outputs = _write_table(selected, output_path / "harmonized_scans")

    audit_rows: list[dict[str, object]] = []
    unit_manifest: dict[str, object] = {}
    for unit in units:
        frame = selected[selected["unit_id"] == unit.id].copy()
        train = frame[frame["split"] == "train"].reset_index(drop=True)
        test = frame[frame["split"] == "test"].reset_index(drop=True)
        train_rss = [parse_rss_json(value) for value in train["rss_json"]]
        test_rss = [parse_rss_json(value) for value in test["rss_json"]]
        train_vocab = training_ap_vocabulary(train_rss)
        diagnostic_vocab = diagnostic_ap_vocabulary(train_rss, test_rss)
        test_union = set().union(*(rss.keys() for rss in test_rss)) if test_rss else set()
        train_union = set(train_vocab)
        test_only = sorted(test_union - train_union)

        unit_dir = unit_root / unit.id
        unit_dir.mkdir(parents=True, exist_ok=True)
        (unit_dir / "ap_vocabulary_train.json").write_text(
            json.dumps(train_vocab, indent=2), encoding="utf-8"
        )
        (unit_dir / "ap_vocabulary_diagnostic.json").write_text(
            json.dumps(diagnostic_vocab, indent=2), encoding="utf-8"
        )
        (unit_dir / "test_only_aps.json").write_text(json.dumps(test_only, indent=2), encoding="utf-8")

        train_x, train_mask = dense_matrix(train_rss, train_vocab)
        test_x, test_mask = dense_matrix(test_rss, train_vocab)
        np.savez_compressed(
            unit_dir / "radio_map_matrices.npz",
            train_rss=train_x,
            train_observed=train_mask,
            test_rss=test_x,
            test_observed=test_mask,
            train_xy=train[["x", "y"]].to_numpy(dtype=np.float64),
            test_xy=test[["x", "y"]].to_numpy(dtype=np.float64),
            train_scan_id=train["scan_id"].astype(str).to_numpy(),
            test_scan_id=test["scan_id"].astype(str).to_numpy(),
        )
        diagnostic_train_x, diagnostic_train_mask = dense_matrix(train_rss, diagnostic_vocab)
        diagnostic_test_x, diagnostic_test_mask = dense_matrix(test_rss, diagnostic_vocab)
        np.savez_compressed(
            unit_dir / "diagnostic_probe_matrices.npz",
            train_rss=diagnostic_train_x,
            train_observed=diagnostic_train_mask,
            test_rss=diagnostic_test_x,
            test_observed=diagnostic_test_mask,
        )
        metadata_columns = [
            "scan_id", "row_id", "split", "x", "y", "floor", "rss_count",
            "source_split", "source_row",
        ]
        _write_table(frame[metadata_columns], unit_dir / "scan_metadata")

        floors = sorted(value for value in frame["floor"].dropna().astype(str).unique())
        row = {
            "unit_id": unit.id,
            "unit_label": unit.label,
            "legacy_label": unit.legacy_label,
            "n_train": len(train),
            "n_test": len(test),
            "n_total": len(frame),
            "floor_labels": "|".join(floors),
            "n_floor_labels": len(floors),
            "floor_labels_available": unit.floor_labels_available,
            "mean_train_rss_count": float(train["rss_count"].mean()),
            "mean_test_rss_count": float(test["rss_count"].mean()),
            "train_ap_vocabulary": len(train_vocab),
            "diagnostic_ap_vocabulary": len(diagnostic_vocab),
            "test_only_ap_count": len(test_only),
            "x_min": float(frame["x"].min()),
            "x_max": float(frame["x"].max()),
            "y_min": float(frame["y"].min()),
            "y_max": float(frame["y"].max()),
            "duplicate_scan_ids": int(frame["scan_id"].duplicated().sum()),
            "invalid_xy": int((~np.isfinite(frame[["x", "y"]].to_numpy(dtype=float))).any(axis=1).sum()),
        }
        audit_rows.append(row)
        unit_manifest[unit.id] = {
            "registry": asdict(unit),
            "audit": row,
            "radio_map_matrix_sha256": sha256_file(unit_dir / "radio_map_matrices.npz"),
            "diagnostic_matrix_sha256": sha256_file(unit_dir / "diagnostic_probe_matrices.npz"),
            "train_vocabulary_sha256": sha256_file(unit_dir / "ap_vocabulary_train.json"),
            "diagnostic_vocabulary_sha256": sha256_file(unit_dir / "ap_vocabulary_diagnostic.json"),
        }

    audit = pd.DataFrame(audit_rows).sort_values("unit_id")
    audit.to_csv(output_path / "unit_harmonization_audit.csv", index=False)
    lineage = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(source_path),
        "source_sha256": sha256_file(source_path),
        "selected_rows": int(len(selected)),
        "training_rows": int((selected["split"] == "train").sum()),
        "test_rows": int((selected["split"] == "test").sum()),
        "canonical_table_outputs": table_outputs,
        "canonical_schema_hash": sha256_text("|".join(canonical_columns)),
        "units": unit_manifest,
    }
    (output_path / "harmonization_manifest.json").write_text(
        json.dumps(lineage, indent=2), encoding="utf-8"
    )
    return lineage
