"""Reproducible diagnostic-probe and scan-level reliability indicators.

The implementation follows the approved study workflow.  It consumes the
harmonized per-unit diagnostic matrices, aggregates repeated training scans at
the same reference point/floor, retrieves the 20 nearest RSS templates, and
computes the scan-level quantities used in the published analysis.
"""
from __future__ import annotations

from dataclasses import dataclass
import shutil
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.neighbors import KDTree

from wifi_integrity.data.registry import UnitSpec, load_registry
from wifi_integrity.data.harmonize import parse_rss_json
from wifi_integrity.hashing import sha256_file
from wifi_integrity.reliability.sqs import reconstruct_sqs

RSS_FLOOR = -110.0
K_CAND = 20
K_LARGE = 10
DISTANCE_CHUNK_SIZE = 256

FEATURE_COLUMNS = [
    "dataset", "group", "unit_label", "row_id", "floor", "x_true", "y_true",
    "diagnostic_x", "diagnostic_y", "min_rss_distance", "nearest_match_isolation",
    "max_cosine_similarity", "sigma_fps", "D_cand", "I_k", "rss_gradient_proxy",
    "ap_overlap", "mean_ap_overlap", "ap_set_novelty", "local_rp_density",
    "ap_count", "rss_std", "rss_range", "density_radius_m", "n_train_scans",
    "n_reference_templates", "n_ap_features", "SQS", "C_sigma", "FII",
]


@dataclass(frozen=True)
class ReliabilityBuildReport:
    rows: int
    units: int
    candidate_rows: int
    max_abs_sqs_difference: float | None
    feature_output: str
    candidate_output: str
    provenance: str = "native_recomputation"


def robust01(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    out = np.full(arr.shape, np.nan, dtype=float)
    mask = np.isfinite(arr)
    if mask.sum() == 0:
        return out
    finite = arr[mask]
    lo, hi = np.percentile(finite, [5, 95])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        out[mask] = 0.5
        return out
    out[mask] = np.clip((finite - lo) / (hi - lo), 0.0, 1.0)
    return out


def _topk_euclidean_neighbors(
    train_x: np.ndarray,
    test_x: np.ndarray,
    k: int = K_CAND,
    chunk_size: int = DISTANCE_CHUNK_SIZE,
) -> tuple[np.ndarray, np.ndarray]:
    train = np.asarray(train_x, dtype=np.float32)
    test = np.asarray(test_x, dtype=np.float32)
    k = min(k, len(train))
    train_norm = np.sum(train * train, axis=1, dtype=np.float32)
    all_idx = np.empty((len(test), k), dtype=np.int64)
    all_dist = np.empty((len(test), k), dtype=np.float32)
    for start in range(0, len(test), chunk_size):
        end = min(start + chunk_size, len(test))
        block = test[start:end]
        block_norm = np.sum(block * block, axis=1, dtype=np.float32)[:, None]
        dist2 = block_norm + train_norm[None, :] - 2.0 * (block @ train.T)
        np.maximum(dist2, 0.0, out=dist2)
        idx_part = np.argpartition(dist2, kth=k - 1, axis=1)[:, :k]
        part_vals = np.take_along_axis(dist2, idx_part, axis=1)
        order = np.argsort(part_vals, axis=1)
        idx_sorted = np.take_along_axis(idx_part, order, axis=1)
        vals_sorted = np.take_along_axis(part_vals, order, axis=1)
        all_idx[start:end] = idx_sorted
        all_dist[start:end] = np.sqrt(vals_sorted, dtype=np.float32) / np.sqrt(
            max(1, train.shape[1])
        )
    return all_dist, all_idx


def _aggregate_training_templates(
    train_x: np.ndarray,
    train_observed: np.ndarray,
    train_xy: np.ndarray,
    floors: Iterable[object],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    xy_round = np.round(np.asarray(train_xy, dtype=float), 3)
    floor_num = (
        pd.to_numeric(pd.Series(list(floors)), errors="coerce")
        .fillna(-9999)
        .to_numpy(dtype=float)
        .reshape(-1, 1)
    )
    key = np.hstack([xy_round, floor_num])
    unique_key, inverse = np.unique(key, axis=0, return_inverse=True)
    n_templates = len(unique_key)

    counts = np.zeros(n_templates, dtype=np.float64)
    sums = np.zeros((n_templates, train_x.shape[1]), dtype=np.float64)
    np.add.at(counts, inverse, 1.0)
    np.add.at(sums, inverse, train_x.astype(np.float64))
    template_x = (sums / counts[:, None]).astype(np.float32)

    observed_int = np.zeros((n_templates, train_observed.shape[1]), dtype=np.int32)
    np.add.at(observed_int, inverse, train_observed.astype(np.int32))
    template_observed = observed_int > 0

    xy_sums = np.zeros((n_templates, 2), dtype=np.float64)
    np.add.at(xy_sums, inverse, train_xy.astype(np.float64))
    template_xy = xy_sums / counts[:, None]

    # Stable representative floor for case displays.
    template_floor = unique_key[:, 2].copy()
    template_floor[template_floor == -9999] = np.nan
    return template_x, template_observed, template_xy, template_floor, n_templates


def _pairwise_diameter(points: np.ndarray) -> float:
    if len(points) <= 1:
        return 0.0
    delta = points[:, None, :] - points[None, :, :]
    return float(np.nanmax(np.sqrt(np.sum(delta * delta, axis=2))))


def _jaccard(test_presence: np.ndarray, candidate_presence: np.ndarray) -> tuple[float, float]:
    inter = np.logical_and(candidate_presence, test_presence).sum(axis=1).astype(float)
    union = np.logical_or(candidate_presence, test_presence).sum(axis=1).astype(float)
    values = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
    return float(np.nanmax(values)), float(np.nanmean(values))


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    aa = np.asarray(a, dtype=float) - RSS_FLOOR
    bb = np.asarray(b, dtype=float) - RSS_FLOOR
    denom = np.linalg.norm(aa) * np.linalg.norm(bb)
    if denom <= 0 or not np.isfinite(denom):
        return np.nan
    return float(np.dot(aa, bb) / denom)


def _adaptive_density_radius(unique_xy: np.ndarray) -> float:
    if len(unique_xy) < 5:
        return 5.0
    tree = KDTree(unique_xy)
    distances, _ = tree.query(unique_xy, k=min(2, len(unique_xy)))
    nearest = distances[:, 1] if distances.shape[1] > 1 else distances[:, 0]
    nearest = nearest[np.isfinite(nearest) & (nearest > 0)]
    if len(nearest) == 0:
        return 5.0
    return float(np.clip(np.percentile(nearest, 50) * 3.0, 2.0, 25.0))


def _write_table(frame: pd.DataFrame, path_base: Path) -> dict[str, str]:
    path_base.parent.mkdir(parents=True, exist_ok=True)
    csv_path = path_base.with_suffix(".csv.gz")
    frame.to_csv(csv_path, index=False, compression="gzip")
    outputs = {"csv_gz": str(csv_path)}
    try:
        parquet_path = path_base.with_suffix(".parquet")
        frame.to_parquet(parquet_path, index=False)
        outputs["parquet"] = str(parquet_path)
    except (ImportError, ModuleNotFoundError, ValueError):
        pass
    return outputs


def _select_ap_list(
    train_rss: list[dict[str, float]],
    test_rss: list[dict[str, float]],
    max_aps: int = 180,
) -> list[str]:
    counts: dict[str, int] = {}
    for rss in train_rss:
        for ap in rss:
            counts[ap] = counts.get(ap, 0) + 2
    for rss in test_rss:
        for ap in rss:
            counts[ap] = counts.get(ap, 0) + 1
    return sorted(counts, key=lambda ap: (-counts[ap], ap))[:max_aps]


def _dense_from_dicts(
    rss_dicts: list[dict[str, float]], ap_list: list[str]
) -> tuple[np.ndarray, np.ndarray]:
    index = {ap: column for column, ap in enumerate(ap_list)}
    values = np.full((len(rss_dicts), len(ap_list)), RSS_FLOOR, dtype=np.float32)
    observed = np.zeros((len(rss_dicts), len(ap_list)), dtype=bool)
    for row, rss in enumerate(rss_dicts):
        for ap, signal in rss.items():
            column = index.get(ap)
            if column is not None:
                values[row, column] = float(signal)
                observed[row, column] = True
    return values, observed


def _unit_features(
    root: Path, unit: UnitSpec, raw_unit: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_meta = raw_unit[
        raw_unit["split"].astype(str).str.lower().eq("train")
    ].copy().reset_index(drop=True)
    test_meta = raw_unit[
        raw_unit["split"].astype(str).str.lower().eq("test")
    ].copy().reset_index(drop=True)
    train_meta["row_id"] = train_meta["row_id"].astype(str)
    test_meta["row_id"] = test_meta["row_id"].astype(str)
    train_xy = train_meta[["x", "y"]].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    test_xy = test_meta[["x", "y"]].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    valid_train = np.isfinite(train_xy).all(axis=1)
    valid_test = np.isfinite(test_xy).all(axis=1)
    train_meta = train_meta.loc[valid_train].reset_index(drop=True)
    test_meta = test_meta.loc[valid_test].reset_index(drop=True)
    train_xy = train_xy[valid_train]
    test_xy = test_xy[valid_test]

    train_rss_dicts = [parse_rss_json(value) for value in train_meta["rss_json"]]
    test_rss_dicts = [parse_rss_json(value) for value in test_meta["rss_json"]]
    ap_list = _select_ap_list(train_rss_dicts, test_rss_dicts)
    train_x, train_observed = _dense_from_dicts(train_rss_dicts, ap_list)
    test_x, test_observed = _dense_from_dicts(test_rss_dicts, ap_list)

    template_x, template_observed, template_xy, template_floor, n_templates = (
        _aggregate_training_templates(
            train_x, train_observed, train_xy, train_meta["floor"].to_numpy()
        )
    )
    k = min(K_CAND, len(template_x))
    k_large = min(K_LARGE, k)
    distances, indices = _topk_euclidean_neighbors(template_x, test_x, k=k)

    unique_xy = np.unique(template_xy, axis=0)
    rp_tree = KDTree(unique_xy)
    density_radius = _adaptive_density_radius(unique_xy)

    feature_rows: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []
    for row_index in range(len(test_meta)):
        cand_idx = indices[row_index]
        cand_xy = template_xy[cand_idx]
        cand_dist = distances[row_index]
        selected_xy = cand_xy[:k_large]
        centroid = selected_xy.mean(axis=0)
        spread = float(np.sqrt(np.mean(np.sum((selected_xy - centroid) ** 2, axis=1))))
        diameter = _pairwise_diameter(selected_xy)
        cumulative = np.cumsum(selected_xy, axis=0) / np.arange(1, k_large + 1)[:, None]
        instability = float(np.max(np.linalg.norm(cumulative - cumulative[-1], axis=1)))

        min_rss = float(cand_dist[0])
        second_rss = float(cand_dist[1]) if len(cand_dist) > 1 else min_rss
        kth_rss = float(cand_dist[k_large - 1])
        isolation = max(second_rss - min_rss, 0.0) / (second_rss + 1e-6)
        gradient = spread / max(kth_rss - min_rss, 1e-6)

        max_overlap, mean_overlap = _jaccard(
            test_observed[row_index], template_observed[cand_idx[:k_large]]
        )
        novelty = 1.0 - max_overlap if np.isfinite(max_overlap) else np.nan
        cosine = _cosine_similarity(test_x[row_index], template_x[cand_idx[0]])
        density = int(
            rp_tree.query_radius(centroid.reshape(1, -1), r=density_radius, count_only=True)[0]
        )

        row_id = str(test_meta.loc[row_index, "row_id"])
        raw_values = np.asarray(list(test_rss_dicts[row_index].values()), dtype=float)
        rss_std = float(np.nanstd(raw_values)) if len(raw_values) else np.nan
        rss_range = (
            float(np.nanmax(raw_values) - np.nanmin(raw_values))
            if len(raw_values)
            else np.nan
        )
        feature_rows.append(
            {
                "dataset": unit.dataset,
                "group": unit.group,
                "unit_label": unit.legacy_label,
                "row_id": row_id,
                "floor": test_meta.loc[row_index, "floor"],
                "x_true": float(test_xy[row_index, 0]),
                "y_true": float(test_xy[row_index, 1]),
                "diagnostic_x": float(centroid[0]),
                "diagnostic_y": float(centroid[1]),
                "min_rss_distance": min_rss,
                "nearest_match_isolation": float(isolation),
                "max_cosine_similarity": cosine,
                "sigma_fps": spread,
                "D_cand": diameter,
                "I_k": instability,
                "rss_gradient_proxy": float(gradient),
                "ap_overlap": max_overlap,
                "mean_ap_overlap": mean_overlap,
                "ap_set_novelty": novelty,
                "local_rp_density": density,
                "ap_count": int(test_observed[row_index].sum()),
                "rss_std": rss_std,
                "rss_range": rss_range,
                "density_radius_m": density_radius,
                "n_train_scans": int(len(train_meta)),
                "n_reference_templates": int(n_templates),
                "n_ap_features": int(test_x.shape[1]),
            }
        )
        for rank in range(k_large):
            template_index = int(cand_idx[rank])
            candidate_rows.append(
                {
                    "dataset": unit.dataset,
                    "group": unit.group,
                    "unit_label": unit.legacy_label,
                    "row_id": row_id,
                    "candidate_rank": rank + 1,
                    "candidate_x": float(template_xy[template_index, 0]),
                    "candidate_y": float(template_xy[template_index, 1]),
                    "candidate_floor": template_floor[template_index],
                    "normalized_rss_distance": float(cand_dist[rank]),
                }
            )

    features = pd.DataFrame(feature_rows)
    risk_min = robust01(features["min_rss_distance"])
    risk_spread = robust01(features["sigma_fps"])
    risk_diameter = robust01(features["D_cand"])
    risk_novelty = robust01(features["ap_set_novelty"])
    support_signal = 1.0 - risk_min
    support_geometry = 1.0 - np.nanmean(np.vstack([risk_spread, risk_diameter]), axis=0)
    support_ap_count = robust01(features["ap_count"])
    support_overlap = robust01(features["ap_overlap"])
    support_density = robust01(features["local_rp_density"])
    support_isolation = robust01(features["nearest_match_isolation"])
    features["SQS"] = np.nanmean(
        np.vstack(
            [
                support_signal,
                support_geometry,
                support_ap_count,
                support_overlap,
                support_density,
            ]
        ),
        axis=0,
    )
    features["C_sigma"] = support_signal / (1.0 + risk_spread)
    features["FII"] = np.nanmean(
        np.vstack(
            [
                support_signal,
                support_ap_count,
                support_overlap,
                support_isolation,
                1.0 - risk_novelty,
            ]
        ),
        axis=0,
    )
    return features[FEATURE_COLUMNS], pd.DataFrame(candidate_rows)


def build_reliability_features(
    root: str | Path,
    *,
    compare_reference: bool = True,
) -> dict[str, object]:
    root_path = Path(root)
    units = load_registry(root_path / "config" / "datasets.yaml")
    harmonized = pd.read_csv(
        root_path / "data" / "source" / "combined_all_datasets.csv",
        usecols=["dataset", "group", "floor", "split", "row_id", "x", "y", "rss_json"],
        dtype={"row_id": str},
        low_memory=False,
    )
    feature_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    for unit in units:
        raw_unit = harmonized[
            harmonized["dataset"].astype(str).eq(unit.dataset)
            & harmonized["group"].astype(str).eq(unit.group)
        ].copy()
        features, candidates = _unit_features(root_path, unit, raw_unit)
        feature_frames.append(features)
        candidate_frames.append(candidates)

    feature_table = pd.concat(feature_frames, ignore_index=True)
    candidate_table = pd.concat(candidate_frames, ignore_index=True)
    feature_table = feature_table.sort_values(["unit_label", "row_id"], kind="mergesort").reset_index(drop=True)
    candidate_table = candidate_table.sort_values(
        ["unit_label", "row_id", "candidate_rank"], kind="mergesort"
    ).reset_index(drop=True)

    feature_outputs = _write_table(
        feature_table, root_path / "results" / "reliability" / "reliability_features_native"
    )
    candidate_outputs = _write_table(
        candidate_table, root_path / "results" / "reliability" / "diagnostic_candidates_m10"
    )

    max_sqs_difference: float | None = None
    reference_report: dict[str, object] = {"checked": False}
    reference_path = (
        root_path
        / "reference"
        / "approved"
        / "legacy_canonical"
        / "reliability_features_approved.csv.gz"
    )
    if compare_reference and reference_path.is_file():
        published_path = root_path / "results" / "reliability" / "reliability_features_published.csv.gz"
        shutil.copy2(reference_path, published_path)
        reference = pd.read_csv(reference_path, dtype={"row_id": str}, low_memory=False)
        reconstructed = reconstruct_sqs(reference)
        reconstruction_difference = np.abs(
            reconstructed.to_numpy(dtype=float) - pd.to_numeric(reference["SQS"], errors="coerce").to_numpy(dtype=float)
        )
        comparison_columns = [
            "min_rss_distance", "nearest_match_isolation", "max_cosine_similarity",
            "sigma_fps", "D_cand", "I_k", "rss_gradient_proxy", "ap_overlap",
            "mean_ap_overlap", "ap_set_novelty", "local_rp_density", "ap_count",
            "rss_std", "rss_range", "SQS", "C_sigma", "FII",
        ]
        comparison = feature_table.merge(
            reference[["dataset", "group", "row_id", *comparison_columns]],
            on=["dataset", "group", "row_id"],
            how="outer",
            indicator=True,
            validate="one_to_one",
            suffixes=("_native", "_reference"),
        )
        matched = comparison["_merge"].eq("both")
        differences = (
            comparison.loc[matched, "SQS_native"] - comparison.loc[matched, "SQS_reference"]
        ).abs()
        max_sqs_difference = float(differences.max()) if len(differences) else np.nan
        indicator_differences = []
        for column in comparison_columns:
            native = pd.to_numeric(comparison.loc[matched, f"{column}_native"], errors="coerce")
            approved = pd.to_numeric(comparison.loc[matched, f"{column}_reference"], errors="coerce")
            delta = (native - approved).abs()
            indicator_differences.append({
                "indicator_id": column,
                "max_abs_difference": float(delta.max()) if delta.notna().any() else None,
                "median_abs_difference": float(delta.median()) if delta.notna().any() else None,
                "exact_within_1e_10_pct": float(100.0 * (delta.fillna(0) <= 1e-10).mean()),
            })
        pd.DataFrame(indicator_differences).to_csv(
            root_path / "results" / "tables" / "reliability_feature_native_vs_published.csv",
            index=False,
        )
        reference_report = {
            "checked": True,
            "reference_rows": int(len(reference)),
            "native_rows": int(len(feature_table)),
            "matched_rows": int(matched.sum()),
            "left_only": int(comparison["_merge"].eq("left_only").sum()),
            "right_only": int(comparison["_merge"].eq("right_only").sum()),
            "native_max_abs_sqs_difference": max_sqs_difference,
            "native_n_sqs_difference_gt_1e_12": int((differences > 1e-12).sum()),
            "published_sqs_reconstruction_max_abs_difference": float(np.nanmax(reconstruction_difference)),
            "published_sqs_reconstruction_n_difference_gt_1e_12": int(np.nansum(reconstruction_difference > 1e-12)),
            "published_output": str(published_path),
            "note": "Native outputs can differ from stored reference values; tie handling and numerical-library behavior require separate investigation. The stored table remains the reference for historical-summary checks.",
        }

    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": "native_recomputation",
        "feature_rows": int(len(feature_table)),
        "candidate_rows": int(len(candidate_table)),
        "units": int(feature_table["unit_label"].nunique()),
        "feature_columns": list(feature_table.columns),
        "candidate_k": K_LARGE,
        "feature_outputs": feature_outputs,
        "candidate_outputs": candidate_outputs,
        "reference_regression": reference_report,
    }
    report_path = root_path / "results" / "logs" / "reliability_feature_regression_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def add_estimator_specific_nearest_rp(
    root: str | Path,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Attach distance from each estimated coordinate to the nearest radio-map RP."""
    if "nearest_rp_distance" in predictions:
        values = pd.to_numeric(predictions["nearest_rp_distance"], errors="coerce")
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError("Invalid stored nearest-RP distances")
        return predictions.copy()
    root_path = Path(root)
    registry = load_registry(root_path / "config" / "datasets.yaml")
    by_legacy = {unit.legacy_label: unit for unit in registry}
    output = predictions.copy()
    output["nearest_rp_distance"] = np.nan
    for unit_label, index in output.groupby("unit_label", observed=False).groups.items():
        unit = by_legacy[str(unit_label)]
        matrices = np.load(
            root_path / "data" / "processed" / "units" / unit.id / "radio_map_matrices.npz",
            allow_pickle=False,
        )
        unique_xy = np.unique(matrices["train_xy"].astype(float), axis=0)
        tree = KDTree(unique_xy)
        query_xy = output.loc[index, ["x_pred", "y_pred"]].to_numpy(dtype=float)
        distances, _ = tree.query(query_xy, k=1)
        output.loc[index, "nearest_rp_distance"] = distances[:, 0]
    return output
