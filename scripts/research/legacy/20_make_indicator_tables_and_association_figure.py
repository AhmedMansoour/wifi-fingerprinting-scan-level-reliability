# ============================================================
# Make scan-level reliability-indicator tables and association figure
# Save as:
#   src/20_make_indicator_tables_and_association_figure.py
#
# Inputs, fixed paths from project root:
#   data/interim/datasets_combined_all/combined_all_datasets.csv
#   data/processed/all_estimator_predictions_10like_units_plus_catboost.csv.gz
#
# Outputs:
#   data/processed/scan_level_reliability_indicator_features.csv.gz
#   results/tables/indicator_error_association_by_condition.csv
#   results/tables/indicator_error_association_summary.csv
#   results/tables/indicator_error_association_estimator_matrix.csv
#   results/figures/fig_indicator_error_association.png/.pdf
#
# This script does NOT search for pre-existing feature/association tables.
# It creates the required scan-level indicator table from the combined dataset
# and the retained estimator prediction file, then computes the association
# tables and the manuscript figure.
# ============================================================

from __future__ import annotations

import os
from pathlib import Path
import json
import math
import warnings
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

from sklearn.neighbors import KDTree


# ============================================================
# Paths
# ============================================================

ROOT = Path(os.environ.get("WIFI_RESEARCH_ROOT", Path(__file__).resolve().parents[3] / "results/research_workspace")).resolve()

COMBINED_PATH = ROOT / "data" / "interim" / "datasets_combined_all" / "combined_all_datasets.csv"
PREDICTION_PATH = ROOT / "data" / "processed" / "all_estimator_predictions_10like_units_plus_catboost.csv.gz"

PROCESSED_DIR = ROOT / "data" / "processed"
TABLE_DIR = ROOT / "results" / "tables"
FIG_DIR = ROOT / "results" / "figures"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_OUT = PROCESSED_DIR / "scan_level_reliability_indicator_features.csv.gz"
ASSOC_OUT = TABLE_DIR / "indicator_error_association_by_condition.csv"
SUMMARY_OUT = TABLE_DIR / "indicator_error_association_summary.csv"
EST_MATRIX_OUT = TABLE_DIR / "indicator_error_association_estimator_matrix.csv"

FIG_OUT = FIG_DIR / "fig_indicator_error_association"


# ============================================================
# Evaluation units and estimators
# ============================================================

ESTIMATOR_ORDER = [
    "KNN",
    "WKNN",
    "Random Forest",
    "Extra Trees",
    "Gradient Boosting",
    "CatBoost",
    "Transformer",
    "Residual CNN",
]

ESTIMATOR_SHORT = {
    "KNN": "KNN",
    "WKNN": "WKNN",
    "Random Forest": "RF",
    "Extra Trees": "ET",
    "Gradient Boosting": "HGB",
    "CatBoost": "Cat",
    "Transformer": "Trf",
    "Residual CNN": "ResCNN",
}

UNIT_ORDER = [
    "BlockZ-10W-1719W / BlockZPolyU",
    "DSI_3778646 / single_area",
    "TAMPERE_MULTIBUILDING_5174851 / SAH1",
    "TAMPERE_MULTIBUILDING_5174851 / TIE1",
    "TAU_ADDITIONAL_3819917 / Database_Building01",
    "TAU_ADDITIONAL_3819917 / Database_Building02",
    "TUT_WLAN_RSS_1161525 / TUT",
    "UJIndoorLoc / Building0",
    "UJIndoorLoc / Building1",
    "UJIndoorLoc / Building2",
    "UJIIndoorLoc / Building0",
    "UJIIndoorLoc / Building1",
    "UJIIndoorLoc / Building2",
]

UNIT_SHORT = {
    "BlockZ-10W-1719W / BlockZPolyU": "Block Z",
    "DSI_3778646 / single_area": "DSI",
    "TAMPERE_MULTIBUILDING_5174851 / SAH1": "Tampere-SAH1",
    "TAMPERE_MULTIBUILDING_5174851 / TIE1": "Tampere-TIE1",
    "TAU_ADDITIONAL_3819917 / Database_Building01": "TAU-B1",
    "TAU_ADDITIONAL_3819917 / Database_Building02": "TAU-B2",
    "TUT_WLAN_RSS_1161525 / TUT": "TUT-WLAN",
    "UJIndoorLoc / Building0": "UJI-B0",
    "UJIndoorLoc / Building1": "UJI-B1",
    "UJIndoorLoc / Building2": "UJI-B2",
    "UJIIndoorLoc / Building0": "UJI-B0",
    "UJIIndoorLoc / Building1": "UJI-B1",
    "UJIIndoorLoc / Building2": "UJI-B2",
}


# ============================================================
# Indicator configuration
# expected_sign:
#   +1: larger raw indicator is expected to mean higher error / higher risk
#   -1: larger raw indicator is expected to mean lower error / stronger support
# aligned_rho = expected_sign * raw_spearman_rho
# ============================================================

INDICATOR_SPECS = [
    {"id": "nearest_rp_distance", "label": "Nearest-RP distance", "family": "Local spatial support", "expected_sign": +1},
    {"id": "I_k", "label": r"$I_k$", "family": "Candidate geometry", "expected_sign": +1},
    {"id": "sigma_fps", "label": r"$\hat{\sigma}_{\mathrm{fps}}$", "family": "Candidate geometry", "expected_sign": +1},
    {"id": "rss_gradient_proxy", "label": "RSS-gradient proxy", "family": "Map ambiguity", "expected_sign": +1},
    {"id": "D_cand", "label": r"$D_{\mathrm{cand}}$", "family": "Candidate geometry", "expected_sign": +1},
    {"id": "SQS", "label": "SQS", "family": "Composite", "expected_sign": -1},
    {"id": "C_sigma", "label": r"$C/\sigma$", "family": "Composite", "expected_sign": -1},
    {"id": "FII", "label": "FII", "family": "Composite", "expected_sign": -1},
    {"id": "local_rp_density", "label": "Local RP density", "family": "Local spatial support", "expected_sign": -1},
    {"id": "ap_set_novelty", "label": "AP-set novelty", "family": "Radio-map compatibility", "expected_sign": +1},
    {"id": "ap_overlap", "label": "AP overlap", "family": "Radio-map compatibility", "expected_sign": -1},
    {"id": "min_rss_distance", "label": "Min RSS distance", "family": "Signal proximity", "expected_sign": +1},
    {"id": "max_cosine_similarity", "label": "Max cosine similarity", "family": "Signal proximity", "expected_sign": -1},
    {"id": "nearest_match_isolation", "label": "Nearest-match isolation", "family": "Signal proximity", "expected_sign": -1},
    {"id": "ap_count", "label": "AP count", "family": "Scan statistics", "expected_sign": -1},
    {"id": "rss_std", "label": "RSS std.", "family": "Scan statistics", "expected_sign": +1},
]

SPEC_BY_ID = {s["id"]: s for s in INDICATOR_SPECS}

FAMILY_COLORS = {
    "Local spatial support": "#0072B2",
    "Candidate geometry": "#D55E00",
    "Map ambiguity": "#CC79A7",
    "Composite": "#009E73",
    "Radio-map compatibility": "#E69F00",
    "Signal proximity": "#7F7F7F",
    "Scan statistics": "#56B4E9",
}


# ============================================================
# Computation settings
# ============================================================

RSS_FLOOR = -110.0
K_CAND = 20
K_SMALL = 3
K_LARGE = 10
MIN_SCANS_FOR_RHO = 8
MAX_APS_PER_UNIT = 180
DISTANCE_CHUNK_SIZE = 256

TOP_N_MAIN = 16
TOP_N_HEATMAP = 10

SAVE_DPI = 500
FIGSIZE = (7.25, 8.6)
HEATMAP_CMAP = "YlGnBu"


# ============================================================
# Matplotlib defaults
# ============================================================

plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": SAVE_DPI,
    "font.family": "serif",
    "font.size": 8.0,
    "axes.titlesize": 8.8,
    "axes.labelsize": 8.2,
    "xtick.labelsize": 7.0,
    "ytick.labelsize": 7.0,
    "legend.fontsize": 6.7,
    "axes.linewidth": 0.65,
    "xtick.major.width": 0.60,
    "ytick.major.width": 0.60,
    "xtick.major.size": 2.8,
    "ytick.major.size": 2.8,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})


# ============================================================
# Utilities
# ============================================================

def ensure_unit_label(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "unit_label" in df.columns:
        df["unit_label"] = df["unit_label"].astype(str)
        return df
    if "unit" in df.columns:
        df["unit_label"] = df["unit"].astype(str)
        return df
    if {"dataset", "group"}.issubset(df.columns):
        df["unit_label"] = df["dataset"].astype(str) + " / " + df["group"].astype(str)
        return df
    raise ValueError("Cannot infer unit label. Need 'unit_label', 'unit', or both 'dataset' and 'group'.")


def unit_sort_key(unit: str) -> int:
    try:
        return UNIT_ORDER.index(unit)
    except ValueError:
        return 999


def parse_rss_json(s) -> Dict[str, float]:
    if pd.isna(s):
        return {}
    if isinstance(s, dict):
        return {str(k): float(v) for k, v in s.items() if pd.notna(v)}
    try:
        obj = json.loads(str(s))
    except Exception:
        return {}
    if not isinstance(obj, dict):
        return {}
    out = {}
    for k, v in obj.items():
        try:
            fv = float(v)
            if math.isfinite(fv):
                out[str(k)] = fv
        except Exception:
            continue
    return out


def robust01(x) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    out = np.full(arr.shape, np.nan, dtype=float)
    mask = np.isfinite(arr)
    if mask.sum() == 0:
        return out
    vals = arr[mask]
    lo, hi = np.percentile(vals, [5, 95])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        out[mask] = 0.5
        return out
    out[mask] = np.clip((vals - lo) / (hi - lo), 0, 1)
    return out


def rank_corr(x, y) -> float:
    tmp = pd.DataFrame({"x": x, "y": y}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(tmp) < MIN_SCANS_FOR_RHO:
        return np.nan
    if tmp["x"].nunique() < 3 or tmp["y"].nunique() < 3:
        return np.nan
    return float(tmp["x"].rank(method="average").corr(tmp["y"].rank(method="average")))



def select_ap_list(train_rss: List[Dict[str, float]], test_rss: List[Dict[str, float]], max_aps: int = MAX_APS_PER_UNIT) -> List[str]:
    """Select frequent APs to keep RSS-neighbor computation fast and stable."""
    counts = {}
    for d in train_rss:
        for ap in d.keys():
            counts[ap] = counts.get(ap, 0) + 2  # training APs get slightly more weight
    for d in test_rss:
        for ap in d.keys():
            counts[ap] = counts.get(ap, 0) + 1
    aps = sorted(counts, key=lambda ap: (-counts[ap], ap))
    return aps[:max_aps]

def topk_euclidean_neighbors(train_X: np.ndarray, test_X: np.ndarray, k: int, chunk_size: int = DISTANCE_CHUNK_SIZE) -> Tuple[np.ndarray, np.ndarray]:
    """Fast brute-force top-k Euclidean neighbors using BLAS-backed matrix products."""
    train = np.asarray(train_X, dtype=np.float32)
    test = np.asarray(test_X, dtype=np.float32)
    n_train = train.shape[0]
    k = min(k, n_train)

    train_norm = np.sum(train * train, axis=1, dtype=np.float32)
    all_idx = np.empty((test.shape[0], k), dtype=np.int64)
    all_dist = np.empty((test.shape[0], k), dtype=np.float32)

    for start in range(0, test.shape[0], chunk_size):
        end = min(start + chunk_size, test.shape[0])
        block = test[start:end]
        block_norm = np.sum(block * block, axis=1, dtype=np.float32)[:, None]
        # squared Euclidean distances
        dist2 = block_norm + train_norm[None, :] - 2.0 * (block @ train.T)
        np.maximum(dist2, 0.0, out=dist2)

        idx_part = np.argpartition(dist2, kth=k - 1, axis=1)[:, :k]
        part_vals = np.take_along_axis(dist2, idx_part, axis=1)
        order = np.argsort(part_vals, axis=1)
        idx_sorted = np.take_along_axis(idx_part, order, axis=1)
        vals_sorted = np.take_along_axis(part_vals, order, axis=1)

        all_idx[start:end] = idx_sorted
        all_dist[start:end] = np.sqrt(vals_sorted, dtype=np.float32) / np.sqrt(max(1, train.shape[1]))

    return all_dist, all_idx

def make_dense_matrix(rss_dicts: List[Dict[str, float]], ap_list: List[str]) -> Tuple[np.ndarray, np.ndarray]:
    ap_index = {ap: j for j, ap in enumerate(ap_list)}
    x = np.full((len(rss_dicts), len(ap_list)), RSS_FLOOR, dtype=np.float32)
    present = np.zeros((len(rss_dicts), len(ap_list)), dtype=bool)

    for i, d in enumerate(rss_dicts):
        for ap, val in d.items():
            j = ap_index.get(ap)
            if j is None:
                continue
            x[i, j] = float(val)
            present[i, j] = True

    return x, present


def safe_xy(df: pd.DataFrame) -> np.ndarray:
    xy = df[["x", "y"]].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=np.float64)
    return xy



def aggregate_training_templates(train_X: np.ndarray, train_present: np.ndarray, train_xy: np.ndarray, floors) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """Aggregate repeated training scans at the same RP/floor into one template."""
    floor_arr = np.asarray(list(floors)).reshape(-1, 1)
    xy_round = np.round(train_xy.astype(float), 3)
    # Use floor in the key when available; NaN floors are converted to a sentinel.
    try:
        floor_num = pd.to_numeric(pd.Series(floor_arr.ravel()), errors="coerce").fillna(-9999).to_numpy(dtype=float).reshape(-1, 1)
    except Exception:
        floor_num = np.full((len(train_xy), 1), -9999.0)
    key = np.hstack([xy_round, floor_num])

    unique_key, inverse = np.unique(key, axis=0, return_inverse=True)
    n_templates = len(unique_key)

    sums = np.zeros((n_templates, train_X.shape[1]), dtype=np.float64)
    counts = np.zeros(n_templates, dtype=np.float64)
    np.add.at(sums, inverse, train_X.astype(np.float64))
    np.add.at(counts, inverse, 1.0)
    template_X = (sums / counts[:, None]).astype(np.float32)

    template_present_int = np.zeros((n_templates, train_present.shape[1]), dtype=np.int16)
    np.add.at(template_present_int, inverse, train_present.astype(np.int16))
    template_present = template_present_int > 0

    xy_sums = np.zeros((n_templates, 2), dtype=np.float64)
    np.add.at(xy_sums, inverse, train_xy.astype(np.float64))
    template_xy = xy_sums / counts[:, None]

    return template_X, template_present, template_xy, n_templates

def pairwise_diameter(points: np.ndarray) -> float:
    if len(points) <= 1:
        return 0.0
    diff = points[:, None, :] - points[None, :, :]
    dist = np.sqrt(np.sum(diff * diff, axis=2))
    return float(np.nanmax(dist))


def mean_jaccard(test_presence: np.ndarray, cand_presence: np.ndarray) -> Tuple[float, float]:
    # Return max and mean Jaccard against candidate scans.
    if cand_presence.size == 0:
        return np.nan, np.nan
    inter = np.logical_and(cand_presence, test_presence).sum(axis=1).astype(float)
    union = np.logical_or(cand_presence, test_presence).sum(axis=1).astype(float)
    jac = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
    return float(np.nanmax(jac)), float(np.nanmean(jac))


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    # Convert from RSS with missing floor into positive signal amplitudes.
    aa = np.asarray(a, dtype=float) - RSS_FLOOR
    bb = np.asarray(b, dtype=float) - RSS_FLOOR
    denom = np.linalg.norm(aa) * np.linalg.norm(bb)
    if denom <= 0 or not np.isfinite(denom):
        return np.nan
    return float(np.dot(aa, bb) / denom)


def adaptive_density_radius(unique_xy: np.ndarray) -> float:
    if len(unique_xy) < 5:
        return 5.0
    tree = KDTree(unique_xy)
    d, _ = tree.query(unique_xy, k=min(2, len(unique_xy)))
    nn = d[:, 1] if d.shape[1] > 1 else d[:, 0]
    nn = nn[np.isfinite(nn) & (nn > 0)]
    if len(nn) == 0:
        return 5.0
    radius = float(np.percentile(nn, 50) * 3.0)
    return float(np.clip(radius, 2.0, 25.0))


# ============================================================
# Build scan-level indicator table
# ============================================================

def load_inputs():
    if not COMBINED_PATH.exists():
        raise FileNotFoundError(f"Combined dataset table not found:\n{COMBINED_PATH}")
    if not PREDICTION_PATH.exists():
        raise FileNotFoundError(f"Prediction file not found:\n{PREDICTION_PATH}")

    print(f"[INFO] Loading prediction file:\n       {PREDICTION_PATH}")
    pred = pd.read_csv(PREDICTION_PATH, dtype={"row_id": str}, low_memory=False)
    pred = ensure_unit_label(pred)
    pred = pred[pred["estimator_display"].isin(ESTIMATOR_ORDER)].copy()

    needed_units = sorted(pred["unit_label"].unique().tolist(), key=unit_sort_key)
    needed_pairs = pred[["dataset", "group"]].drop_duplicates()
    pair_set = set(map(tuple, needed_pairs[["dataset", "group"]].astype(str).to_numpy()))

    print(f"[INFO] Loading combined dataset table:\n       {COMBINED_PATH}")
    usecols = ["dataset", "group", "floor", "split", "row_id", "x", "y", "rss_json", "rss_count"]
    combined = pd.read_csv(COMBINED_PATH, usecols=usecols, dtype={"row_id": str}, low_memory=False)
    combined = ensure_unit_label(combined)
    combined = combined[combined[["dataset", "group"]].astype(str).apply(tuple, axis=1).isin(pair_set)].copy()

    print(f"[INFO] Prediction rows: {len(pred):,}")
    print(f"[INFO] Combined rows for retained units: {len(combined):,}")
    print(f"[INFO] Units: {len(needed_units)}")
    for u in needed_units:
        print(f"       - {u}")

    return combined, pred, needed_units


def build_unit_features(unit: str, combined: pd.DataFrame, pred_unit: pd.DataFrame) -> pd.DataFrame:
    dataset = str(pred_unit["dataset"].iloc[0])
    group = str(pred_unit["group"].iloc[0])
    test_ids = set(pred_unit["row_id"].astype(str).unique())

    unit_df = combined[(combined["dataset"].astype(str) == dataset) & (combined["group"].astype(str) == group)].copy()
    train_df = unit_df[unit_df["split"].astype(str).str.lower().eq("train")].copy()
    test_df = unit_df[unit_df["row_id"].astype(str).isin(test_ids)].copy()

    if train_df.empty:
        raise RuntimeError(f"No training rows found for unit {unit}")
    if test_df.empty:
        raise RuntimeError(f"No test rows matching prediction row_id found for unit {unit}")

    # Keep only valid coordinates.
    train_xy = safe_xy(train_df)
    test_xy = safe_xy(test_df)
    valid_train = np.isfinite(train_xy).all(axis=1)
    valid_test = np.isfinite(test_xy).all(axis=1)
    train_df = train_df.loc[valid_train].reset_index(drop=True)
    test_df = test_df.loc[valid_test].reset_index(drop=True)
    train_xy = train_xy[valid_train]
    test_xy = test_xy[valid_test]

    print(f"[INFO] Processing {unit}: train={len(train_df):,}, test={len(test_df):,}")

    train_rss = [parse_rss_json(s) for s in train_df["rss_json"].tolist()]
    test_rss = [parse_rss_json(s) for s in test_df["rss_json"].tolist()]

    ap_list = select_ap_list(train_rss, test_rss, MAX_APS_PER_UNIT)

    if not ap_list:
        raise RuntimeError(f"No APs detected for unit {unit}")

    print(f"       AP features used for diagnostic retrieval: {len(ap_list):,}")

    train_X, train_present = make_dense_matrix(train_rss, ap_list)
    test_X, test_present = make_dense_matrix(test_rss, ap_list)

    train_X, train_present, train_xy, n_templates = aggregate_training_templates(
        train_X, train_present, train_xy, train_df["floor"].to_numpy()
    )
    print(f"       Reference templates after RP aggregation: {n_templates:,}")

    k = min(K_CAND, len(train_X))
    k_small = min(K_SMALL, k)
    k_large = min(K_LARGE, k)

    dists, idx = topk_euclidean_neighbors(train_X, test_X, k=k, chunk_size=DISTANCE_CHUNK_SIZE)

    # Unique RP tree for local density and estimator-specific nearest-RP distance.
    unique_xy = np.unique(train_xy, axis=0)
    rp_tree = KDTree(unique_xy)
    density_radius = adaptive_density_radius(unique_xy)

    rows = []

    for i in range(len(test_df)):
        cand_idx = idx[i]
        cand_xy = train_xy[cand_idx]
        cand_d = dists[i]
        centroid_all = np.mean(cand_xy[:k_large], axis=0)
        centroid_large = np.mean(cand_xy[:k_large], axis=0)

        spread = np.sqrt(np.mean(np.sum((cand_xy[:k_large] - centroid_large) ** 2, axis=1)))
        diam = pairwise_diameter(cand_xy[:k_large])

        # K-sensitivity / retrieval instability: how much the diagnostic
        # coordinate changes as the neighbor count grows from 1 to K_LARGE.
        cumulative_centroids = np.cumsum(cand_xy[:k_large], axis=0) / np.arange(1, k_large + 1)[:, None]
        ik = float(np.max(np.linalg.norm(cumulative_centroids - cumulative_centroids[-1], axis=1)))

        min_rss = float(cand_d[0])
        second_rss = float(cand_d[1]) if len(cand_d) > 1 else min_rss
        kth_rss = float(cand_d[k_large - 1]) if len(cand_d) >= k_large else float(cand_d[-1])

        gap = max(second_rss - min_rss, 0.0)
        isolation = gap / (second_rss + 1e-6)
        contrast = max(kth_rss - min_rss, 1e-6)
        grad_proxy = spread / contrast

        cand_presence = train_present[cand_idx[:k_large]]
        max_jac, mean_jac = mean_jaccard(test_present[i], cand_presence)
        novelty = 1.0 - max_jac if np.isfinite(max_jac) else np.nan

        max_cos = cosine_sim(test_X[i], train_X[cand_idx[0]])

        density_count = int(rp_tree.query_radius(centroid_all.reshape(1, -1), r=density_radius, count_only=True)[0])

        rss_values = np.asarray(list(test_rss[i].values()), dtype=float)
        if len(rss_values) == 0:
            rss_std = np.nan
            rss_range = np.nan
        else:
            rss_std = float(np.nanstd(rss_values))
            rss_range = float(np.nanmax(rss_values) - np.nanmin(rss_values))

        rows.append({
            "dataset": dataset,
            "group": group,
            "unit_label": unit,
            "row_id": str(test_df["row_id"].iloc[i]),
            "floor": test_df["floor"].iloc[i],
            "x_true": float(test_xy[i, 0]),
            "y_true": float(test_xy[i, 1]),
            "diagnostic_x": float(centroid_all[0]),
            "diagnostic_y": float(centroid_all[1]),
            "min_rss_distance": min_rss,
            "nearest_match_isolation": isolation,
            "max_cosine_similarity": max_cos,
            "sigma_fps": float(spread),
            "D_cand": float(diam),
            "I_k": ik,
            "rss_gradient_proxy": float(grad_proxy),
            "ap_overlap": float(max_jac),
            "mean_ap_overlap": float(mean_jac),
            "ap_set_novelty": float(novelty),
            "local_rp_density": density_count,
            "ap_count": int(test_present[i].sum()),
            "rss_std": rss_std,
            "rss_range": rss_range,
            "density_radius_m": density_radius,
            "n_train_scans": len(train_df),
            "n_reference_templates": len(train_X),
            "n_ap_features": len(ap_list),
        })

    features = pd.DataFrame(rows)

    # Unit-wise robust normalization for composite support/confidence indicators.
    # Larger SQS, C/sigma, and FII represent stronger reliability support.
    risk_min_rss = robust01(features["min_rss_distance"])
    risk_spread = robust01(features["sigma_fps"])
    risk_diam = robust01(features["D_cand"])
    risk_grad = robust01(features["rss_gradient_proxy"])
    risk_novelty = robust01(features["ap_set_novelty"])

    sup_signal = 1.0 - risk_min_rss
    sup_geometry = 1.0 - np.nanmean(np.vstack([risk_spread, risk_diam]), axis=0)
    sup_ap_count = robust01(features["ap_count"])
    sup_overlap = robust01(features["ap_overlap"])
    sup_density = robust01(features["local_rp_density"])
    sup_isolation = robust01(features["nearest_match_isolation"])

    features["SQS"] = np.nanmean(
        np.vstack([sup_signal, sup_geometry, sup_ap_count, sup_overlap, sup_density]),
        axis=0,
    )
    features["C_sigma"] = sup_signal / (1.0 + risk_spread)
    features["FII"] = np.nanmean(
        np.vstack([sup_signal, sup_ap_count, sup_overlap, sup_isolation, 1.0 - risk_novelty]),
        axis=0,
    )

    return features


def build_scan_level_feature_table(combined: pd.DataFrame, pred: pd.DataFrame, units: List[str]) -> pd.DataFrame:
    frames = []
    for unit in units:
        pred_unit = pred[pred["unit_label"] == unit].copy()
        feat = build_unit_features(unit, combined, pred_unit)
        frames.append(feat)

    features = pd.concat(frames, ignore_index=True)
    features.to_csv(FEATURE_OUT, index=False, compression="gzip")
    print(f"[INFO] Wrote scan-level feature table:\n       {FEATURE_OUT}\n       rows={len(features):,}, columns={len(features.columns):,}")
    return features


# ============================================================
# Association tables
# ============================================================

def add_estimator_specific_nearest_rp(long_df: pd.DataFrame, combined: pd.DataFrame) -> pd.DataFrame:
    long_df = long_df.copy()
    long_df["nearest_rp_distance"] = np.nan

    for unit, gidx in long_df.groupby("unit_label", observed=False).groups.items():
        unit_rows = long_df.loc[gidx]
        dataset = str(unit_rows["dataset"].iloc[0])
        group = str(unit_rows["group"].iloc[0])
        train = combined[
            (combined["dataset"].astype(str) == dataset) &
            (combined["group"].astype(str) == group) &
            (combined["split"].astype(str).str.lower() == "train")
        ].copy()
        xy = safe_xy(train)
        xy = xy[np.isfinite(xy).all(axis=1)]
        if len(xy) == 0:
            continue
        unique_xy = np.unique(xy, axis=0)
        tree = KDTree(unique_xy)

        pred_xy = long_df.loc[gidx, ["x_pred", "y_pred"]].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        valid = np.isfinite(pred_xy).all(axis=1)
        d = np.full(len(pred_xy), np.nan, dtype=float)
        if valid.any():
            dd, _ = tree.query(pred_xy[valid], k=1)
            d[valid] = dd[:, 0]
        long_df.loc[gidx, "nearest_rp_distance"] = d

    return long_df


def build_long_indicator_error_table(features: pd.DataFrame, pred: pd.DataFrame, combined: pd.DataFrame) -> pd.DataFrame:
    keep_pred = ["dataset", "group", "unit_label", "row_id", "estimator_display", "error_m", "x_pred", "y_pred"]
    pred_small = pred[keep_pred].copy()
    pred_small["row_id"] = pred_small["row_id"].astype(str)

    features_small = features.copy()
    features_small["row_id"] = features_small["row_id"].astype(str)

    # Avoid duplicated true coordinate columns from prediction table.
    drop_cols = [c for c in ["x_true", "y_true"] if c in features_small.columns]
    if drop_cols:
        features_small = features_small.drop(columns=drop_cols)

    long_df = pred_small.merge(
        features_small,
        on=["dataset", "group", "unit_label", "row_id"],
        how="left",
        validate="many_to_one",
    )

    if long_df[["min_rss_distance", "sigma_fps"]].isna().all().any():
        raise RuntimeError("Feature merge failed: key indicator columns are all NaN after merging.")

    long_df = add_estimator_specific_nearest_rp(long_df, combined)
    return long_df


def compute_association_tables(long_df: pd.DataFrame):
    rows = []

    for spec in INDICATOR_SPECS:
        iid = spec["id"]
        if iid not in long_df.columns:
            print(f"[WARN] Indicator not found in long table, skipped: {iid}")
            continue

        long_df[iid] = pd.to_numeric(long_df[iid], errors="coerce")

        for (unit, est), g in long_df.groupby(["unit_label", "estimator_display"], observed=False):
            rho = rank_corr(g[iid], g["error_m"])
            if not np.isfinite(rho):
                continue

            n_valid = int(pd.DataFrame({"x": g[iid], "y": g["error_m"]}).replace([np.inf, -np.inf], np.nan).dropna().shape[0])

            rows.append({
                "indicator_id": iid,
                "label": spec["label"],
                "family": spec["family"],
                "expected_sign": spec["expected_sign"],
                "unit_label": unit,
                "unit_short": UNIT_SHORT.get(unit, unit),
                "estimator_display": est,
                "estimator_short": ESTIMATOR_SHORT.get(est, est),
                "n_valid_scans": n_valid,
                "rho": rho,
                "aligned_rho": rho * spec["expected_sign"],
            })

    assoc = pd.DataFrame(rows)
    if assoc.empty:
        raise RuntimeError("No valid indicator-error associations were computed.")

    summary = (
        assoc
        .groupby(["indicator_id", "label", "family"], observed=False)
        .agg(
            n_conditions=("aligned_rho", "count"),
            median_aligned_rho=("aligned_rho", "median"),
            q25_aligned_rho=("aligned_rho", lambda x: np.percentile(x, 25)),
            q75_aligned_rho=("aligned_rho", lambda x: np.percentile(x, 75)),
            mean_aligned_rho=("aligned_rho", "mean"),
            direction_consistency_pct=("aligned_rho", lambda x: 100.0 * np.mean(np.asarray(x) > 0)),
        )
        .reset_index()
        .sort_values(["median_aligned_rho", "direction_consistency_pct", "n_conditions"], ascending=[False, False, False])
        .reset_index(drop=True)
    )

    est_matrix = (
        assoc
        .pivot_table(index="indicator_id", columns="estimator_display", values="aligned_rho", aggfunc="median")
        .reindex(index=summary["indicator_id"].tolist(), columns=ESTIMATOR_ORDER)
        .reset_index()
    )
    est_matrix = summary[["indicator_id", "label", "family"]].merge(est_matrix, on="indicator_id", how="left")

    assoc.to_csv(ASSOC_OUT, index=False)
    summary.to_csv(SUMMARY_OUT, index=False)
    est_matrix.to_csv(EST_MATRIX_OUT, index=False)

    print(f"[INFO] Wrote association tables:\n       {ASSOC_OUT}\n       {SUMMARY_OUT}\n       {EST_MATRIX_OUT}")
    print("[INFO] Top indicator associations:")
    print(summary[["label", "median_aligned_rho", "direction_consistency_pct", "n_conditions"]].head(12).to_string(index=False))

    return assoc, summary, est_matrix


# ============================================================
# Figure
# ============================================================

def style_common(ax):
    ax.tick_params(direction="in", top=True, right=True)
    ax.grid(True, axis="x", color="0.86", linewidth=0.42, alpha=0.70)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_linewidth(0.65)


def panel_a_ranked_dot_interval(ax, assoc: pd.DataFrame, summary_main: pd.DataFrame):
    order = summary_main["indicator_id"].tolist()
    y_pos = np.arange(len(order))
    label_map = dict(zip(summary_main["indicator_id"], summary_main["label"]))
    family_map = dict(zip(summary_main["indicator_id"], summary_main["family"]))

    for i, iid in enumerate(order):
        g = assoc[assoc["indicator_id"] == iid]
        xvals = g["aligned_rho"].to_numpy(dtype=float)
        color = FAMILY_COLORS.get(family_map[iid], "0.35")

        rng = np.random.default_rng(2026 + i)
        jitter = rng.uniform(-0.13, 0.13, size=len(xvals)) if len(xvals) else []
        ax.scatter(xvals, np.full(len(xvals), i, dtype=float) + jitter, s=8, color="0.75", alpha=0.55, edgecolor="none", zorder=1)

        row = summary_main[summary_main["indicator_id"] == iid].iloc[0]
        med = float(row["median_aligned_rho"])
        q25 = float(row["q25_aligned_rho"])
        q75 = float(row["q75_aligned_rho"])
        ax.hlines(i, q25, q75, color=color, linewidth=2.0, zorder=3)
        ax.scatter(med, i, s=26, color=color, edgecolor="black", linewidth=0.35, zorder=4)

    ax.axvline(0, color="0.25", linewidth=0.75, linestyle="--")
    ax.set_yticks(y_pos)
    ax.set_yticklabels([label_map[iid] for iid in order])
    ax.invert_yaxis()
    ax.set_xlabel("Aligned Spearman association")
    ax.set_title("(a) Ranked indicator--error association", loc="left", pad=3)
    ax.xaxis.set_major_locator(MaxNLocator(5))
    style_common(ax)


def panel_b_consistency(ax, summary_main: pd.DataFrame):
    y_pos = np.arange(len(summary_main))
    vals = summary_main["direction_consistency_pct"].to_numpy(dtype=float)
    colors = [FAMILY_COLORS.get(f, "0.35") for f in summary_main["family"]]

    ax.barh(y_pos, vals, color=colors, edgecolor="0.35", linewidth=0.35, height=0.64, zorder=3)

    for y, val, n in zip(y_pos, vals, summary_main["n_conditions"].to_numpy(dtype=int)):
        if val < 92:
            ax.text(val + 1.2, y, f"{val:.0f}% ({n})", va="center", ha="left", fontsize=6.4, color="0.20")
        else:
            ax.text(val - 1.2, y, f"{val:.0f}% ({n})", va="center", ha="right", fontsize=6.4, color="0.20")

    ax.axvline(50, color="0.25", linewidth=0.75, linestyle="--")
    ax.set_xlim(0, 103)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([""] * len(summary_main))
    ax.invert_yaxis()
    ax.set_xlabel("Expected-direction consistency (%)")
    ax.set_title("(b) Direction consistency", loc="left", pad=3)
    ax.xaxis.set_major_locator(MaxNLocator(5))
    style_common(ax)


def panel_c_estimator_heatmap(ax, assoc: pd.DataFrame, summary: pd.DataFrame):
    top_ids = summary.head(TOP_N_HEATMAP)["indicator_id"].tolist()

    mat = (
        assoc[assoc["indicator_id"].isin(top_ids)]
        .pivot_table(index="indicator_id", columns="estimator_display", values="aligned_rho", aggfunc="median")
        .reindex(index=top_ids, columns=ESTIMATOR_ORDER)
    )

    label_map = dict(zip(summary["indicator_id"], summary["label"]))
    data = mat.to_numpy(dtype=float)
    finite = data[np.isfinite(data)]
    vmax = max(float(np.percentile(finite, 95)), 0.25) if finite.size else 0.25

    im = ax.imshow(data, aspect="auto", cmap=HEATMAP_CMAP, vmin=0.0, vmax=vmax)

    ax.set_xticks(np.arange(len(ESTIMATOR_ORDER)))
    ax.set_xticklabels([ESTIMATOR_SHORT[e] for e in ESTIMATOR_ORDER], rotation=0)
    ax.set_yticks(np.arange(len(top_ids)))
    ax.set_yticklabels([label_map[iid] for iid in top_ids])
    ax.set_title("(c) Estimator-wise median aligned association", loc="left", pad=3)

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data[i, j]
            if np.isfinite(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=5.7, color="black" if val < vmax * 0.65 else "white")

    ax.tick_params(direction="in", top=True, right=True)
    for spine in ax.spines.values():
        spine.set_linewidth(0.65)

    cbar = plt.colorbar(im, ax=ax, fraction=0.028, pad=0.015)
    cbar.set_label("Median aligned Spearman", fontsize=7.0)
    cbar.ax.tick_params(labelsize=6.3, direction="in")


def add_family_legend(fig, summary_main: pd.DataFrame):
    families = []
    for f in summary_main["family"].tolist():
        if f not in families:
            families.append(f)
    handles = [Patch(facecolor=FAMILY_COLORS.get(f, "0.35"), edgecolor="0.35", linewidth=0.35, label=f) for f in families]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.008), ncol=3, frameon=False, columnspacing=1.1, handlelength=1.2, handletextpad=0.45)


def build_figure(assoc: pd.DataFrame, summary: pd.DataFrame):
    summary_main = summary.head(TOP_N_MAIN).copy()

    fig = plt.figure(figsize=FIGSIZE)
    gs = fig.add_gridspec(
        nrows=3,
        ncols=2,
        height_ratios=[1.55, 0.82, 1.35],
        width_ratios=[1.35, 0.95],
        hspace=0.34,
        wspace=0.08,
    )

    ax_a = fig.add_subplot(gs[0:2, 0])
    ax_b = fig.add_subplot(gs[0:2, 1])
    ax_c = fig.add_subplot(gs[2, :])

    panel_a_ranked_dot_interval(ax_a, assoc, summary_main)
    panel_b_consistency(ax_b, summary_main)
    panel_c_estimator_heatmap(ax_c, assoc, summary)
    add_family_legend(fig, summary_main)

    fig.subplots_adjust(left=0.17, right=0.985, top=0.975, bottom=0.095)

    fig.savefig(FIG_OUT.with_suffix(".png"), dpi=SAVE_DPI, bbox_inches="tight", pad_inches=0.025)
    fig.savefig(FIG_OUT.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.025)
    plt.close(fig)

    print(f"[INFO] Saved figure:\n       {FIG_OUT.with_suffix('.png')}\n       {FIG_OUT.with_suffix('.pdf')}")


# ============================================================
# Main
# ============================================================

def main():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)

        combined, pred, units = load_inputs()
        features = build_scan_level_feature_table(combined, pred, units)
        long_df = build_long_indicator_error_table(features, pred, combined)
        assoc, summary, est_matrix = compute_association_tables(long_df)
        build_figure(assoc, summary)

    print("[INFO] Done.")


if __name__ == "__main__":
    main()
