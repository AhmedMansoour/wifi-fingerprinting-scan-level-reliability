# ============================================================
# Build condition-adaptive gross-error discrimination analysis
# Save as:
#   src/21_build_gross_error_discrimination.py
#
# This script supports Section:
#   \subsection{Gross-Error Discrimination}
#   \label{sec:results_gross_error}
#
# Inputs:
#   data/processed/all_estimator_predictions_10like_units_plus_catboost.csv.gz
#   data/processed/scan_level_reliability_indicator_features.csv.gz
#   data/interim/datasets_combined_all/combined_all_datasets.csv
#
# Outputs:
#   results/figures/fig_gross_error_discrimination.png/.pdf
#
#   results/tables/gross_error_thresholds_by_condition.csv
#   results/tables/gross_error_discrimination_by_condition.csv
#   results/tables/gross_error_discrimination_summary.csv
#   results/tables/gross_error_discrimination_estimator_matrix_auroc.csv
#   results/tables/gross_error_discrimination_estimator_matrix_auprc.csv
#   results/tables/gross_error_prevalence_matrix.csv
#
# Definition:
#   For each evaluation unit u and estimator m:
#
#       tau_{u,m} = Q75(E_{u,m}) + 1.5 IQR(E_{u,m})
#
#   A scan is a condition-adaptive gross-error case if:
#
#       error_m > tau_{u,m}
#
# No fixed meter-level gross-error threshold is used.
# ============================================================

import os
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.neighbors import KDTree


# ============================================================
# Paths
# ============================================================

ROOT = Path(os.environ.get("WIFI_RESEARCH_ROOT", Path(__file__).resolve().parents[3] / "results/research_workspace")).resolve()

PREDICTION_PATH = ROOT / "data" / "processed" / "all_estimator_predictions_10like_units_plus_catboost.csv.gz"
FEATURE_PATH = ROOT / "data" / "processed" / "scan_level_reliability_indicator_features.csv.gz"
COMBINED_PATH = ROOT / "data" / "interim" / "datasets_combined_all" / "combined_all_datasets.csv"

FIG_DIR = ROOT / "results" / "figures"
TABLE_DIR = ROOT / "results" / "tables"

FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Estimator order and labels
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


# ============================================================
# Unit order and labels
# ============================================================

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
#
# expected_sign:
#   +1: larger raw value means higher risk / larger error
#   -1: larger raw value means stronger support / lower risk
#
# aligned score for discrimination:
#   z = expected_sign * indicator
#
# so larger z consistently means stronger evidence of gross-error risk.
# ============================================================

INDICATOR_SPECS = [
    {"id": "SQS", "label": "SQS", "family": "Composite", "expected_sign": -1},
    {"id": "nearest_rp_distance", "label": "Nearest-RP distance", "family": "Local spatial support", "expected_sign": +1},
    {"id": "sigma_fps", "label": r"$\hat{\sigma}_{\mathrm{fps}}$", "family": "Candidate geometry", "expected_sign": +1},
    {"id": "I_k", "label": r"$I_k$", "family": "Candidate geometry", "expected_sign": +1},
    {"id": "rss_gradient_proxy", "label": "RSS-gradient proxy", "family": "Map ambiguity", "expected_sign": +1},
    {"id": "D_cand", "label": r"$D_{\mathrm{cand}}$", "family": "Candidate geometry", "expected_sign": +1},
    {"id": "local_rp_density", "label": "Local RP density", "family": "Local spatial support", "expected_sign": -1},
    {"id": "FII", "label": "FII", "family": "Composite", "expected_sign": -1},
    {"id": "C_sigma", "label": r"$C/\sigma$", "family": "Composite", "expected_sign": -1},
    {"id": "ap_overlap", "label": "AP overlap", "family": "Radio-map compatibility", "expected_sign": -1},
    {"id": "mean_ap_overlap", "label": "Mean AP overlap", "family": "Radio-map compatibility", "expected_sign": -1},
    {"id": "ap_set_novelty", "label": "AP-set novelty", "family": "Radio-map compatibility", "expected_sign": +1},
    {"id": "max_cosine_similarity", "label": "Max cosine similarity", "family": "Signal proximity", "expected_sign": -1},
    {"id": "min_rss_distance", "label": "Min RSS distance", "family": "Signal proximity", "expected_sign": +1},
    {"id": "nearest_match_isolation", "label": "Nearest-match isolation", "family": "Signal proximity", "expected_sign": -1},
    {"id": "ap_count", "label": "AP count", "family": "Scan statistics", "expected_sign": -1},
    {"id": "rss_std", "label": "RSS std.", "family": "Scan statistics", "expected_sign": +1},
    {"id": "rss_range", "label": "RSS range", "family": "Scan statistics", "expected_sign": +1},
]

SPEC_BY_ID = {s["id"]: s for s in INDICATOR_SPECS}

FAMILY_COLORS = {
    "Composite": "#009E73",
    "Local spatial support": "#0072B2",
    "Candidate geometry": "#D55E00",
    "Map ambiguity": "#CC79A7",
    "Radio-map compatibility": "#E69F00",
    "Signal proximity": "#7F7F7F",
    "Scan statistics": "#56B4E9",
}


# ============================================================
# Settings
# ============================================================

MIN_SCANS_FOR_METRIC = 20
MIN_GROSS_CASES = 3
MIN_NORMAL_CASES = 3

TOP_N_MAIN = 14
TOP_N_HEATMAP = 10

SAVE_DPI = 500
FIGSIZE = (7.25, 9.20)

PREVALENCE_CMAP = "YlOrRd"
AUROC_CMAP = "YlGnBu"


# ============================================================
# Matplotlib defaults
# ============================================================

plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": SAVE_DPI,
    "font.family": "serif",
    "font.size": 8.0,
    "axes.titlesize": 8.8,
    "axes.labelsize": 8.1,
    "xtick.labelsize": 6.8,
    "ytick.labelsize": 6.8,
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
# Utility functions
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

    raise ValueError("Cannot infer unit label. Need unit_label, unit, or both dataset and group.")


def unit_sort_key(unit: str) -> int:
    try:
        return UNIT_ORDER.index(unit)
    except ValueError:
        return 999


def safe_xy(df: pd.DataFrame) -> np.ndarray:
    x_col = "x" if "x" in df.columns else "x_true"
    y_col = "y" if "y" in df.columns else "y_true"

    if x_col not in df.columns or y_col not in df.columns:
        raise ValueError("Cannot find coordinate columns. Expected x/y or x_true/y_true.")

    return df[[x_col, y_col]].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)


def finite_xy(df: pd.DataFrame, x_col="x_pred", y_col="y_pred") -> np.ndarray:
    return df[[x_col, y_col]].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)


def add_estimator_specific_nearest_rp(long_df: pd.DataFrame, combined: pd.DataFrame) -> pd.DataFrame:
    """Compute distance from each predicted coordinate to nearest training RP.

    This indicator is estimator-specific because it depends on x_pred/y_pred.
    """
    long_df = long_df.copy()
    long_df["nearest_rp_distance"] = np.nan

    print("[INFO] Computing estimator-specific nearest-RP distance...")

    for unit, gidx in long_df.groupby("unit_label", observed=False).groups.items():
        unit_rows = long_df.loc[gidx]
        dataset = str(unit_rows["dataset"].iloc[0])
        group = str(unit_rows["group"].iloc[0])

        train = combined[
            (combined["dataset"].astype(str) == dataset) &
            (combined["group"].astype(str) == group) &
            (combined["split"].astype(str).str.lower() == "train")
        ].copy()

        if train.empty:
            print(f"[WARN] No training rows found for {unit}. nearest_rp_distance left as NaN.")
            continue

        xy_train = safe_xy(train)
        xy_train = xy_train[np.isfinite(xy_train).all(axis=1)]

        if len(xy_train) == 0:
            print(f"[WARN] No finite training coordinates found for {unit}. nearest_rp_distance left as NaN.")
            continue

        unique_xy = np.unique(xy_train, axis=0)
        tree = KDTree(unique_xy)

        pred_xy = finite_xy(long_df.loc[gidx], "x_pred", "y_pred")
        valid = np.isfinite(pred_xy).all(axis=1)

        d = np.full(len(pred_xy), np.nan, dtype=float)
        if valid.any():
            dd, _ = tree.query(pred_xy[valid], k=1)
            d[valid] = dd[:, 0]

        long_df.loc[gidx, "nearest_rp_distance"] = d

    return long_df


def load_inputs():
    if not PREDICTION_PATH.exists():
        raise FileNotFoundError(f"Missing prediction file:\n{PREDICTION_PATH}")

    if not FEATURE_PATH.exists():
        raise FileNotFoundError(
            f"Missing scan-level feature table:\n{FEATURE_PATH}\n"
            "Run src/20_make_indicator_tables_and_association_figure.py first."
        )

    if not COMBINED_PATH.exists():
        raise FileNotFoundError(f"Missing combined dataset table:\n{COMBINED_PATH}")

    print(f"[INFO] Loading predictions:\n       {PREDICTION_PATH}")
    pred = pd.read_csv(PREDICTION_PATH, dtype={"row_id": str}, low_memory=False)
    pred = ensure_unit_label(pred)

    print(f"[INFO] Loading scan-level reliability feature table:\n       {FEATURE_PATH}")
    features = pd.read_csv(FEATURE_PATH, dtype={"row_id": str}, low_memory=False)
    features = ensure_unit_label(features)

    print(f"[INFO] Loading combined dataset table:\n       {COMBINED_PATH}")
    combined = pd.read_csv(COMBINED_PATH, low_memory=False)
    combined = ensure_unit_label(combined)

    pred["estimator_display"] = pred["estimator_display"].astype(str)
    pred = pred[pred["estimator_display"].isin(ESTIMATOR_ORDER)].copy()

    pred["error_m"] = pd.to_numeric(pred["error_m"], errors="coerce")
    pred = pred[np.isfinite(pred["error_m"])].copy()

    print(f"[INFO] Prediction rows: {len(pred):,}")
    print(f"[INFO] Feature rows: {len(features):,}")
    print(f"[INFO] Combined rows: {len(combined):,}")

    return pred, features, combined


def build_long_table(pred: pd.DataFrame, features: pd.DataFrame, combined: pd.DataFrame) -> pd.DataFrame:
    keep_pred = [
        "dataset", "group", "unit_label", "row_id",
        "estimator_display", "error_m", "x_pred", "y_pred",
    ]
    keep_pred = [c for c in keep_pred if c in pred.columns]

    pred_small = pred[keep_pred].copy()
    pred_small["row_id"] = pred_small["row_id"].astype(str)

    features_small = features.copy()
    features_small["row_id"] = features_small["row_id"].astype(str)

    # Avoid duplicate true coordinate columns in the merged long table.
    drop_cols = [c for c in ["x_true", "y_true"] if c in features_small.columns]
    if drop_cols:
        features_small = features_small.drop(columns=drop_cols)

    long_df = pred_small.merge(
        features_small,
        on=["dataset", "group", "unit_label", "row_id"],
        how="left",
        validate="many_to_one",
    )

    missing_core = long_df[["min_rss_distance", "sigma_fps", "SQS"]].isna().mean()
    if (missing_core > 0.95).any():
        raise RuntimeError(
            "Feature merge appears to have failed because key indicator columns are mostly NaN:\n"
            f"{missing_core}"
        )

    long_df = add_estimator_specific_nearest_rp(long_df, combined)

    return long_df


# ============================================================
# Gross-error labels
# ============================================================

def compute_condition_thresholds(long_df: pd.DataFrame):
    rows = []

    for (unit, est), g in long_df.groupby(["unit_label", "estimator_display"], observed=False):
        err = pd.to_numeric(g["error_m"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)

        if len(err) == 0:
            continue

        q25 = float(np.percentile(err, 25))
        q50 = float(np.percentile(err, 50))
        q75 = float(np.percentile(err, 75))
        iqr = q75 - q25
        tau = q75 + 1.5 * iqr

        gross = err > tau
        n = int(len(err))
        n_gross = int(gross.sum())
        prevalence = 100.0 * n_gross / n if n > 0 else np.nan

        rows.append({
            "unit_label": unit,
            "unit_short": UNIT_SHORT.get(unit, unit),
            "estimator_display": est,
            "estimator_short": ESTIMATOR_SHORT.get(est, est),
            "n_scans": n,
            "q25_error_m": q25,
            "median_error_m": q50,
            "q75_error_m": q75,
            "iqr_error_m": iqr,
            "adaptive_threshold_m": tau,
            "n_gross_error": n_gross,
            "gross_error_prevalence_pct": prevalence,
        })

    thresholds = pd.DataFrame(rows)
    thresholds["unit_order"] = thresholds["unit_label"].map(unit_sort_key)
    thresholds["estimator_order"] = thresholds["estimator_display"].map(lambda e: ESTIMATOR_ORDER.index(e) if e in ESTIMATOR_ORDER else 999)
    thresholds = thresholds.sort_values(["unit_order", "estimator_order"]).drop(columns=["unit_order", "estimator_order"])

    return thresholds


def attach_gross_error_labels(long_df: pd.DataFrame, thresholds: pd.DataFrame) -> pd.DataFrame:
    df = long_df.merge(
        thresholds[["unit_label", "estimator_display", "adaptive_threshold_m"]],
        on=["unit_label", "estimator_display"],
        how="left",
        validate="many_to_one",
    )

    df["gross_error"] = (
        pd.to_numeric(df["error_m"], errors="coerce") >
        pd.to_numeric(df["adaptive_threshold_m"], errors="coerce")
    ).astype(int)

    return df


# ============================================================
# Discrimination metrics
# ============================================================

def compute_auc_metrics(y_true, score):
    tmp = pd.DataFrame({"y": y_true, "score": score})
    tmp = tmp.replace([np.inf, -np.inf], np.nan).dropna()

    if len(tmp) < MIN_SCANS_FOR_METRIC:
        return None

    y = tmp["y"].astype(int).to_numpy()
    s = tmp["score"].astype(float).to_numpy()

    n = int(len(y))
    n_pos = int(y.sum())
    n_neg = int(n - n_pos)

    if n_pos < MIN_GROSS_CASES or n_neg < MIN_NORMAL_CASES:
        return None

    try:
        auroc = float(roc_auc_score(y, s))
    except Exception:
        auroc = np.nan

    try:
        auprc = float(average_precision_score(y, s))
    except Exception:
        auprc = np.nan

    prevalence = n_pos / n
    auprc_lift = auprc / prevalence if prevalence > 0 and np.isfinite(auprc) else np.nan

    return {
        "n_valid_scans": n,
        "n_gross_error": n_pos,
        "n_normal": n_neg,
        "gross_error_prevalence_pct": 100.0 * prevalence,
        "auroc": auroc,
        "auprc": auprc,
        "auprc_baseline": prevalence,
        "auprc_lift": auprc_lift,
    }


def compute_discrimination_tables(long_df: pd.DataFrame):
    rows = []

    available_indicators = [s for s in INDICATOR_SPECS if s["id"] in long_df.columns]

    print("[INFO] Indicators used for gross-error discrimination:")
    for spec in available_indicators:
        print(f"       - {spec['id']} ({spec['label']})")

    for spec in available_indicators:
        iid = spec["id"]
        label = spec["label"]
        family = spec["family"]
        sign = spec["expected_sign"]

        raw_values = pd.to_numeric(long_df[iid], errors="coerce")
        long_df[f"aligned_{iid}"] = sign * raw_values

        for (unit, est), g in long_df.groupby(["unit_label", "estimator_display"], observed=False):
            metrics = compute_auc_metrics(g["gross_error"], g[f"aligned_{iid}"])

            if metrics is None:
                continue

            rows.append({
                "indicator_id": iid,
                "label": label,
                "family": family,
                "expected_sign": sign,
                "unit_label": unit,
                "unit_short": UNIT_SHORT.get(unit, unit),
                "estimator_display": est,
                "estimator_short": ESTIMATOR_SHORT.get(est, est),
                **metrics,
            })

    by_condition = pd.DataFrame(rows)

    if by_condition.empty:
        raise RuntimeError("No valid gross-error discrimination metrics could be computed.")

    summary = (
        by_condition
        .groupby(["indicator_id", "label", "family"], observed=False)
        .agg(
            n_conditions=("auroc", "count"),
            median_auroc=("auroc", "median"),
            q25_auroc=("auroc", lambda x: np.percentile(x, 25)),
            q75_auroc=("auroc", lambda x: np.percentile(x, 75)),
            mean_auroc=("auroc", "mean"),
            median_auprc=("auprc", "median"),
            q25_auprc=("auprc", lambda x: np.percentile(x, 25)),
            q75_auprc=("auprc", lambda x: np.percentile(x, 75)),
            mean_auprc=("auprc", "mean"),
            median_auprc_lift=("auprc_lift", "median"),
            median_prevalence_pct=("gross_error_prevalence_pct", "median"),
        )
        .reset_index()
    )

    summary = summary.sort_values(
        ["median_auroc", "median_auprc", "n_conditions"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    estimator_matrix_auroc = (
        by_condition
        .pivot_table(
            index="indicator_id",
            columns="estimator_display",
            values="auroc",
            aggfunc="median",
        )
        .reindex(index=summary["indicator_id"], columns=ESTIMATOR_ORDER)
        .reset_index()
    )

    estimator_matrix_auprc = (
        by_condition
        .pivot_table(
            index="indicator_id",
            columns="estimator_display",
            values="auprc",
            aggfunc="median",
        )
        .reindex(index=summary["indicator_id"], columns=ESTIMATOR_ORDER)
        .reset_index()
    )

    meta = summary[["indicator_id", "label", "family"]]
    estimator_matrix_auroc = meta.merge(estimator_matrix_auroc, on="indicator_id", how="left")
    estimator_matrix_auprc = meta.merge(estimator_matrix_auprc, on="indicator_id", how="left")

    return by_condition, summary, estimator_matrix_auroc, estimator_matrix_auprc


def compute_prevalence_matrix(thresholds: pd.DataFrame):
    units = sorted(thresholds["unit_label"].unique(), key=unit_sort_key)

    mat = (
        thresholds
        .pivot_table(
            index="unit_label",
            columns="estimator_display",
            values="gross_error_prevalence_pct",
            aggfunc="first",
        )
        .reindex(index=units, columns=ESTIMATOR_ORDER)
    )

    return mat


# ============================================================
# Plotting
# ============================================================

def style_metric_axis(ax):
    ax.tick_params(direction="in", top=True, right=True)
    ax.grid(True, axis="x", color="0.86", linewidth=0.42, alpha=0.70)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_linewidth(0.65)


def draw_ranked_metric_panel(ax, by_condition, summary, metric, title, xlabel, top_n=TOP_N_MAIN):
    metric_col = metric
    q25_col = f"q25_{metric.replace('median_', '')}" if metric.startswith("median_") else None
    q75_col = f"q75_{metric.replace('median_', '')}" if metric.startswith("median_") else None

    # Determine columns for intervals.
    if metric == "median_auroc":
        q25_col, q75_col = "q25_auroc", "q75_auroc"
        value_col_condition = "auroc"
    elif metric == "median_auprc":
        q25_col, q75_col = "q25_auprc", "q75_auprc"
        value_col_condition = "auprc"
    else:
        raise ValueError(metric)

    main = summary.sort_values(metric_col, ascending=False).head(top_n).copy()
    order = main["indicator_id"].tolist()
    y = np.arange(len(order))

    for i, iid in enumerate(order):
        row = main[main["indicator_id"] == iid].iloc[0]
        family = row["family"]
        color = FAMILY_COLORS.get(family, "0.35")

        vals = by_condition.loc[by_condition["indicator_id"] == iid, value_col_condition].to_numpy(dtype=float)
        vals = vals[np.isfinite(vals)]

        if len(vals) > 0:
            rng = np.random.default_rng(2026 + i)
            jitter = rng.uniform(-0.13, 0.13, size=len(vals))
            ax.scatter(
                vals,
                np.full_like(vals, i, dtype=float) + jitter,
                s=8,
                color="0.75",
                alpha=0.48,
                edgecolor="none",
                zorder=1,
            )

        med = float(row[metric_col])
        q25 = float(row[q25_col])
        q75 = float(row[q75_col])

        ax.hlines(i, q25, q75, color=color, linewidth=2.0, zorder=3)
        ax.scatter(
            med,
            i,
            s=25,
            color=color,
            edgecolor="black",
            linewidth=0.35,
            zorder=4,
        )

    ax.set_yticks(y)
    ax.set_yticklabels(main["label"].tolist())
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", pad=3)
    ax.xaxis.set_major_locator(MaxNLocator(5))
    style_metric_axis(ax)

    if metric == "median_auroc":
        ax.axvline(0.5, color="0.25", linewidth=0.75, linestyle="--")
        ax.set_xlim(0.40, 1.00)
    else:
        ax.set_xlim(0.0, max(0.25, min(1.0, np.nanmax(by_condition["auprc"].to_numpy(dtype=float)) * 1.10)))


def draw_prevalence_heatmap(ax, prevalence_matrix: pd.DataFrame):
    data = prevalence_matrix.to_numpy(dtype=float)
    units = prevalence_matrix.index.tolist()
    estimators = prevalence_matrix.columns.tolist()

    vmax = max(5.0, np.nanpercentile(data, 95)) if np.isfinite(data).any() else 10.0
    im = ax.imshow(data, aspect="auto", cmap=PREVALENCE_CMAP, vmin=0, vmax=vmax)

    ax.set_xticks(np.arange(len(estimators)))
    ax.set_xticklabels([ESTIMATOR_SHORT.get(e, e) for e in estimators])
    ax.set_yticks(np.arange(len(units)))
    ax.set_yticklabels([UNIT_SHORT.get(u, u) for u in units])

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data[i, j]
            if np.isfinite(val):
                ax.text(
                    j, i, f"{val:.1f}",
                    ha="center", va="center",
                    fontsize=5.9,
                    color="black" if val < vmax * 0.63 else "white",
                )

    ax.set_title("(a) Adaptive gross-error prevalence (%)", loc="left", pad=3)
    ax.tick_params(direction="in", top=True, right=True)
    for spine in ax.spines.values():
        spine.set_linewidth(0.65)

    cbar = plt.colorbar(im, ax=ax, fraction=0.024, pad=0.012)
    cbar.set_label("Gross-error prevalence (%)", fontsize=7.0)
    cbar.ax.tick_params(labelsize=6.3, direction="in")


def draw_estimator_heatmap(ax, by_condition, summary):
    top_ids = summary.head(TOP_N_HEATMAP)["indicator_id"].tolist()

    mat = (
        by_condition[by_condition["indicator_id"].isin(top_ids)]
        .pivot_table(
            index="indicator_id",
            columns="estimator_display",
            values="auroc",
            aggfunc="median",
        )
        .reindex(index=top_ids, columns=ESTIMATOR_ORDER)
    )

    labels = {
        row["indicator_id"]: row["label"]
        for _, row in summary[summary["indicator_id"].isin(top_ids)].iterrows()
    }

    data = mat.to_numpy(dtype=float)

    im = ax.imshow(data, aspect="auto", cmap=AUROC_CMAP, vmin=0.5, vmax=1.0)

    ax.set_xticks(np.arange(len(ESTIMATOR_ORDER)))
    ax.set_xticklabels([ESTIMATOR_SHORT[e] for e in ESTIMATOR_ORDER])
    ax.set_yticks(np.arange(len(top_ids)))
    ax.set_yticklabels([labels[iid] for iid in top_ids])

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data[i, j]
            if np.isfinite(val):
                ax.text(
                    j, i, f"{val:.2f}",
                    ha="center",
                    va="center",
                    fontsize=5.7,
                    color="black" if val < 0.74 else "white",
                )

    ax.set_title("(d) Estimator-wise median AUROC", loc="left", pad=3)
    ax.tick_params(direction="in", top=True, right=True)
    for spine in ax.spines.values():
        spine.set_linewidth(0.65)

    cbar = plt.colorbar(im, ax=ax, fraction=0.024, pad=0.012)
    cbar.set_label("Median AUROC", fontsize=7.0)
    cbar.ax.tick_params(labelsize=6.3, direction="in")


def add_family_legend(fig, summary):
    families = []
    for f in summary["family"].tolist():
        if f not in families:
            families.append(f)

    handles = [
        Patch(
            facecolor=FAMILY_COLORS.get(f, "0.35"),
            edgecolor="0.35",
            linewidth=0.35,
            label=f,
        )
        for f in families
    ]

    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.008),
        ncol=3,
        frameon=False,
        columnspacing=1.1,
        handlelength=1.2,
        handletextpad=0.45,
    )


def build_figure(thresholds, by_condition, summary):
    prevalence_matrix = compute_prevalence_matrix(thresholds)

    fig = plt.figure(figsize=FIGSIZE)

    gs = fig.add_gridspec(
        nrows=3,
        ncols=2,
        height_ratios=[1.15, 1.38, 1.28],
        width_ratios=[1.0, 1.0],
        hspace=0.38,
        wspace=0.40,
    )

    ax_a = fig.add_subplot(gs[0, :])
    ax_b = fig.add_subplot(gs[1, 0])
    ax_c = fig.add_subplot(gs[1, 1])
    ax_d = fig.add_subplot(gs[2, :])

    draw_prevalence_heatmap(ax_a, prevalence_matrix)
    draw_ranked_metric_panel(
        ax_b,
        by_condition,
        summary,
        metric="median_auroc",
        title="(b) Gross-error ranking by AUROC",
        xlabel="AUROC",
        top_n=TOP_N_MAIN,
    )
    draw_ranked_metric_panel(
        ax_c,
        by_condition,
        summary,
        metric="median_auprc",
        title="(c) Gross-error ranking by AUPRC",
        xlabel="AUPRC",
        top_n=TOP_N_MAIN,
    )
    draw_estimator_heatmap(ax_d, by_condition, summary)

    add_family_legend(fig, summary)

    fig.subplots_adjust(
        left=0.145,
        right=0.985,
        top=0.975,
        bottom=0.085,
    )

    out = FIG_DIR / "fig_gross_error_discrimination"
    fig.savefig(out.with_suffix(".png"), dpi=SAVE_DPI, bbox_inches="tight", pad_inches=0.025)
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.025)
    plt.close(fig)

    print(f"[INFO] Saved figure:\n       {out.with_suffix('.png')}\n       {out.with_suffix('.pdf')}")


# ============================================================
# Main
# ============================================================

def main():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        pred, features, combined = load_inputs()
        long_df = build_long_table(pred, features, combined)

        thresholds = compute_condition_thresholds(long_df)
        long_df = attach_gross_error_labels(long_df, thresholds)

        by_condition, summary, est_mat_auroc, est_mat_auprc = compute_discrimination_tables(long_df)

    prevalence_matrix = compute_prevalence_matrix(thresholds)

    thresholds_path = TABLE_DIR / "gross_error_thresholds_by_condition.csv"
    by_condition_path = TABLE_DIR / "gross_error_discrimination_by_condition.csv"
    summary_path = TABLE_DIR / "gross_error_discrimination_summary.csv"
    est_auroc_path = TABLE_DIR / "gross_error_discrimination_estimator_matrix_auroc.csv"
    est_auprc_path = TABLE_DIR / "gross_error_discrimination_estimator_matrix_auprc.csv"
    prevalence_path = TABLE_DIR / "gross_error_prevalence_matrix.csv"

    thresholds.to_csv(thresholds_path, index=False)
    by_condition.to_csv(by_condition_path, index=False)
    summary.to_csv(summary_path, index=False)
    est_mat_auroc.to_csv(est_auroc_path, index=False)
    est_mat_auprc.to_csv(est_auprc_path, index=False)
    prevalence_matrix.to_csv(prevalence_path)

    print("\n[INFO] Wrote gross-error tables:")
    for p in [
        thresholds_path,
        by_condition_path,
        summary_path,
        est_auroc_path,
        est_auprc_path,
        prevalence_path,
    ]:
        print(f"       {p}")

    print("\n[INFO] Adaptive gross-error prevalence summary:")
    print(
        thresholds[["gross_error_prevalence_pct"]]
        .describe(percentiles=[0.25, 0.5, 0.75])
        .to_string()
    )

    print("\n[INFO] Top gross-error discriminators by median AUROC:")
    print(
        summary[
            [
                "label",
                "median_auroc",
                "q25_auroc",
                "q75_auroc",
                "median_auprc",
                "median_auprc_lift",
                "n_conditions",
            ]
        ]
        .head(12)
        .to_string(index=False)
    )

    build_figure(thresholds, by_condition, summary)

    print("\n[INFO] Done.")


if __name__ == "__main__":
    main()
