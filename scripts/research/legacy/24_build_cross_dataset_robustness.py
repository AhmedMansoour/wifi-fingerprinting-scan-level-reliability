# ============================================================
# Build cross-dataset robustness and portability analysis
#
# Save as:
#   src/24_build_cross_dataset_robustness.py
#
# Run from project root:
# Historical local working directory omitted; use WIFI_RESEARCH_ROOT.
#   %run src/24_build_cross_dataset_robustness.py
#
# Purpose:
#   This script supports:
#
#       \subsection{Cross-Dataset Robustness and Portability}
#       \label{sec:robustness}
#
#   It combines:
#     (i)   continuous indicator-error association results,
#     (ii)  direction consistency and valid-condition coverage,
#     (iii) estimator-wise portability,
#     (iv)  gross-error discrimination under adaptive-IQR and fixed 7 m labels.
#
# Inputs expected from previous runs:
#   results/tables/indicator_error_association_by_condition.csv
#   results/tables/indicator_error_association_summary.csv
#
#   results/tables/gross_error_discrimination_summary_adaptive_iqr.csv
#   results/tables/gross_error_discrimination_summary_fixed_7m.csv
#   results/tables/gross_error_discrimination_by_condition_adaptive_iqr.csv
#   results/tables/gross_error_discrimination_by_condition_fixed_7m.csv
#
# Outputs:
#   results/figures/fig_cross_dataset_robustness.png
#   results/figures/fig_cross_dataset_robustness.pdf
#
#   results/tables/cross_dataset_robustness_summary.csv
#   results/tables/cross_dataset_robustness_by_unit.csv
#   results/tables/cross_dataset_robustness_estimator_matrix.csv
#   results/tables/cross_dataset_robustness_gross_error_comparison.csv
#
# Main robustness index:
#
#   R_j = 100 * C_j * D_j * A_j / max_l A_l
#
#   where:
#     A_j = median positive aligned Spearman association,
#     D_j = direction-consistency fraction,
#     C_j = valid-condition coverage fraction.
#
#   Larger R_j means that the indicator is simultaneously strong,
#   directionally stable, and available across evaluation conditions.
# ============================================================

import os
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator


# ============================================================
# Paths and configuration
# ============================================================

ROOT = Path(os.environ.get("WIFI_RESEARCH_ROOT", Path(__file__).resolve().parents[3] / "results/research_workspace")).resolve()
FIG_DIR = ROOT / "results" / "figures"
TABLE_DIR = ROOT / "results" / "tables"

FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

ASSOC_BY_CONDITION_PATH = TABLE_DIR / "indicator_error_association_by_condition.csv"
ASSOC_SUMMARY_PATH = TABLE_DIR / "indicator_error_association_summary.csv"

GE_ADAPTIVE_SUMMARY_PATH = TABLE_DIR / "gross_error_discrimination_summary_adaptive_iqr.csv"
GE_FIXED_SUMMARY_PATH = TABLE_DIR / "gross_error_discrimination_summary_fixed_7m.csv"
GE_ADAPTIVE_BY_CONDITION_PATH = TABLE_DIR / "gross_error_discrimination_by_condition_adaptive_iqr.csv"
GE_FIXED_BY_CONDITION_PATH = TABLE_DIR / "gross_error_discrimination_by_condition_fixed_7m.csv"

OUT_SUMMARY = TABLE_DIR / "cross_dataset_robustness_summary.csv"
OUT_BY_UNIT = TABLE_DIR / "cross_dataset_robustness_by_unit.csv"
OUT_ESTIMATOR = TABLE_DIR / "cross_dataset_robustness_estimator_matrix.csv"
OUT_GE = TABLE_DIR / "cross_dataset_robustness_gross_error_comparison.csv"

OUT_FIG = FIG_DIR / "fig_cross_dataset_robustness"

SAVE_DPI = 500
FIGSIZE = (7.25, 8.60)

TOP_N_BARS = 12
TOP_N_HEATMAP = 8

MAX_CONDITIONS_EXPECTED = 80  # 10 units x 8 retained reference estimators

ASSOC_COLOR = "#0072B2"
GE_ADAPTIVE_COLOR = "#009E73"
GE_FIXED_COLOR = "#D55E00"
COVERAGE_COLOR = "#7F7F7F"
HEATMAP_CMAP = "YlGnBu"


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

UNIT_SHORT_FALLBACK = {
    "BlockZ-10W-1719W / BlockZPolyU": "HK-Z",
    "DSI_3778646 / single_area": "DSI",
    "TAMPERE_MULTIBUILDING_5174851 / SAH1": "Tam-SAH1",
    "TAMPERE_MULTIBUILDING_5174851 / TIE1": "Tam-TIE1",
    "TAU_ADDITIONAL_3819917 / Database_Building01": "TAU-B1",
    "TAU_ADDITIONAL_3819917 / Database_Building02": "TAU-B2",
    "TUT_WLAN_RSS_1161525 / TUT": "TUT",
    "UJIndoorLoc / Building0": "UJI-B0",
    "UJIndoorLoc / Building1": "UJI-B1",
    "UJIndoorLoc / Building2": "UJI-B2",
    "UJIIndoorLoc / Building0": "UJI-B0",
    "UJIIndoorLoc / Building1": "UJI-B1",
    "UJIIndoorLoc / Building2": "UJI-B2",
}

UNIT_ORDER_HINTS = [
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


plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": SAVE_DPI,
    "font.family": "serif",
    "font.size": 8.0,
    "axes.titlesize": 8.8,
    "axes.labelsize": 8.0,
    "xtick.labelsize": 6.8,
    "ytick.labelsize": 6.8,
    "legend.fontsize": 6.8,
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

def read_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found:\n{path}\n\n"
            "Run the previous analysis scripts first:\n"
            "  %run src/20_make_indicator_tables_and_association_figure.py\n"
            "  %run src/22_build_gross_error_fixed_threshold_sensitivity_7m.py"
        )
    return pd.read_csv(path)


def finite_series(s):
    return pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan)


def q25(x):
    x = finite_series(pd.Series(x)).dropna()
    return float(np.percentile(x, 25)) if len(x) else np.nan


def q75(x):
    x = finite_series(pd.Series(x)).dropna()
    return float(np.percentile(x, 75)) if len(x) else np.nan


def first_existing_column(df: pd.DataFrame, candidates, required=True, name="column"):
    for c in candidates:
        if c in df.columns:
            return c
    if required:
        raise KeyError(
            f"Could not find {name}. Tried: {candidates}\n"
            f"Available columns: {list(df.columns)}"
        )
    return None


def safe_unit_short(unit):
    return UNIT_SHORT_FALLBACK.get(unit, unit)


def unit_sort_key(unit):
    if unit in UNIT_ORDER_HINTS:
        return UNIT_ORDER_HINTS.index(unit)
    # Also handle UJI/UJ spelling differences.
    alt = unit.replace("UJIIndoorLoc", "UJIndoorLoc")
    if alt in UNIT_ORDER_HINTS:
        return UNIT_ORDER_HINTS.index(alt)
    return 999


def estimator_sort_key(est):
    return ESTIMATOR_ORDER.index(est) if est in ESTIMATOR_ORDER else 999


def standardize_indicator_id(df: pd.DataFrame):
    id_col = first_existing_column(
        df,
        ["indicator_id", "indicator", "id", "feature_id", "metric_id"],
        required=True,
        name="indicator id",
    )
    if id_col != "indicator_id":
        df = df.rename(columns={id_col: "indicator_id"})
    return df


def standardize_label_family(df: pd.DataFrame):
    if "label" not in df.columns:
        if "indicator_label" in df.columns:
            df = df.rename(columns={"indicator_label": "label"})
        else:
            df["label"] = df["indicator_id"]

    if "family" not in df.columns:
        if "indicator_family" in df.columns:
            df = df.rename(columns={"indicator_family": "family"})
        else:
            df["family"] = "Unspecified"

    return df


def infer_condition_columns(df: pd.DataFrame):
    unit_col = first_existing_column(
        df,
        ["unit_label", "unit", "condition_unit", "building", "dataset_unit"],
        required=True,
        name="unit label",
    )
    est_col = first_existing_column(
        df,
        ["estimator_display", "estimator", "model", "reference_estimator"],
        required=True,
        name="estimator label",
    )
    return unit_col, est_col


def infer_aligned_association_column(df: pd.DataFrame):
    return first_existing_column(
        df,
        [
            "aligned_rho",
            "aligned_spearman",
            "aligned_spearman_rho",
            "rho_aligned",
            "spearman_aligned",
            "aligned_corr",
            "aligned_correlation",
            "median_aligned_rho",   # fallback if a summary-like table is passed
        ],
        required=True,
        name="aligned association column",
    )


def infer_summary_columns(summary: pd.DataFrame, by_condition: pd.DataFrame):
    median_col = first_existing_column(
        summary,
        [
            "median_aligned_rho",
            "median_aligned_spearman",
            "median_aligned_association",
            "median_rho_aligned",
            "median_aligned_corr",
        ],
        required=False,
        name="summary median aligned association",
    )

    consistency_col = first_existing_column(
        summary,
        [
            "direction_consistency_pct",
            "direction_consistency_percent",
            "expected_direction_consistency_pct",
            "sign_consistency_pct",
            "positive_direction_pct",
        ],
        required=False,
        name="direction consistency percent",
    )

    n_conditions_col = first_existing_column(
        summary,
        ["n_conditions", "valid_conditions", "n_valid_conditions", "count"],
        required=False,
        name="valid condition count",
    )

    return median_col, consistency_col, n_conditions_col


# ============================================================
# Robustness computations
# ============================================================

def prepare_association_tables():
    assoc = read_required_csv(ASSOC_BY_CONDITION_PATH)
    summary = read_required_csv(ASSOC_SUMMARY_PATH)

    assoc = standardize_indicator_id(assoc)
    summary = standardize_indicator_id(summary)
    assoc = standardize_label_family(assoc)
    summary = standardize_label_family(summary)

    unit_col, est_col = infer_condition_columns(assoc)
    aligned_col = infer_aligned_association_column(assoc)

    assoc = assoc.rename(columns={
        unit_col: "unit_label",
        est_col: "estimator_display",
        aligned_col: "aligned_association",
    })

    assoc["aligned_association"] = finite_series(assoc["aligned_association"])
    assoc["unit_short"] = assoc["unit_label"].map(safe_unit_short)
    assoc["estimator_short"] = assoc["estimator_display"].map(lambda x: ESTIMATOR_SHORT.get(x, x))

    median_col, consistency_col, n_conditions_col = infer_summary_columns(summary, assoc)

    # Build a robust summary from by-condition table first.
    computed = (
        assoc.groupby(["indicator_id", "label", "family"], observed=False)
        .agg(
            n_conditions=("aligned_association", lambda x: int(finite_series(x).notna().sum())),
            median_aligned_association=("aligned_association", "median"),
            q25_aligned_association=("aligned_association", q25),
            q75_aligned_association=("aligned_association", q75),
            direction_consistency_pct=("aligned_association", lambda x: 100.0 * np.nanmean(finite_series(x) > 0)),
            n_units=("unit_label", lambda x: int(pd.Series(x).nunique())),
            n_estimators=("estimator_display", lambda x: int(pd.Series(x).nunique())),
        )
        .reset_index()
    )

    # If summary has official values, merge them and prefer them where available.
    keep_cols = ["indicator_id"]
    rename = {}

    if median_col:
        keep_cols.append(median_col)
        rename[median_col] = "summary_median_aligned_association"
    if consistency_col:
        keep_cols.append(consistency_col)
        rename[consistency_col] = "summary_direction_consistency_pct"
    if n_conditions_col:
        keep_cols.append(n_conditions_col)
        rename[n_conditions_col] = "summary_n_conditions"

    if len(keep_cols) > 1:
        s2 = summary[keep_cols].rename(columns=rename).drop_duplicates("indicator_id")
        computed = computed.merge(s2, on="indicator_id", how="left")

        if "summary_median_aligned_association" in computed.columns:
            computed["median_aligned_association"] = computed["summary_median_aligned_association"].combine_first(
                computed["median_aligned_association"]
            )
        if "summary_direction_consistency_pct" in computed.columns:
            computed["direction_consistency_pct"] = computed["summary_direction_consistency_pct"].combine_first(
                computed["direction_consistency_pct"]
            )
        if "summary_n_conditions" in computed.columns:
            computed["n_conditions"] = computed["summary_n_conditions"].combine_first(
                computed["n_conditions"]
            ).astype(int)

    computed["coverage_fraction"] = computed["n_conditions"] / float(MAX_CONDITIONS_EXPECTED)
    computed["direction_consistency_fraction"] = computed["direction_consistency_pct"] / 100.0
    computed["median_positive_aligned_association"] = computed["median_aligned_association"].clip(lower=0)

    max_assoc = computed["median_positive_aligned_association"].max()
    if not np.isfinite(max_assoc) or max_assoc <= 0:
        max_assoc = 1.0

    computed["normalized_association_strength"] = computed["median_positive_aligned_association"] / max_assoc
    computed["robustness_index"] = (
        100.0
        * computed["coverage_fraction"].clip(0, 1)
        * computed["direction_consistency_fraction"].clip(0, 1)
        * computed["normalized_association_strength"].clip(0, 1)
    )

    computed = computed.sort_values(
        ["robustness_index", "median_aligned_association", "direction_consistency_pct"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    return assoc, computed


def build_by_unit(assoc: pd.DataFrame, summary: pd.DataFrame):
    top_ids = summary.head(TOP_N_HEATMAP)["indicator_id"].tolist()

    by_unit = (
        assoc[assoc["indicator_id"].isin(top_ids)]
        .groupby(["indicator_id", "label", "family", "unit_label", "unit_short"], observed=False)
        .agg(
            median_aligned_association=("aligned_association", "median"),
            q25_aligned_association=("aligned_association", q25),
            q75_aligned_association=("aligned_association", q75),
            n_estimators=("estimator_display", "nunique"),
            n_conditions=("aligned_association", lambda x: int(finite_series(x).notna().sum())),
            direction_consistency_pct=("aligned_association", lambda x: 100.0 * np.nanmean(finite_series(x) > 0)),
        )
        .reset_index()
    )

    by_unit["unit_order"] = by_unit["unit_label"].map(unit_sort_key)
    by_unit["indicator_order"] = by_unit["indicator_id"].map({iid: i for i, iid in enumerate(top_ids)})
    by_unit = by_unit.sort_values(["indicator_order", "unit_order"]).drop(columns=["indicator_order", "unit_order"])

    return by_unit


def build_estimator_matrix(assoc: pd.DataFrame, summary: pd.DataFrame):
    top_ids = summary.head(TOP_N_HEATMAP)["indicator_id"].tolist()

    est = (
        assoc[assoc["indicator_id"].isin(top_ids)]
        .groupby(["indicator_id", "label", "family", "estimator_display", "estimator_short"], observed=False)
        .agg(
            median_aligned_association=("aligned_association", "median"),
            q25_aligned_association=("aligned_association", q25),
            q75_aligned_association=("aligned_association", q75),
            n_units=("unit_label", "nunique"),
            n_conditions=("aligned_association", lambda x: int(finite_series(x).notna().sum())),
            direction_consistency_pct=("aligned_association", lambda x: 100.0 * np.nanmean(finite_series(x) > 0)),
        )
        .reset_index()
    )

    est["estimator_order"] = est["estimator_display"].map(estimator_sort_key)
    est["indicator_order"] = est["indicator_id"].map({iid: i for i, iid in enumerate(top_ids)})
    est = est.sort_values(["indicator_order", "estimator_order"]).drop(columns=["indicator_order", "estimator_order"])

    return est


def build_gross_error_comparison(summary: pd.DataFrame):
    adaptive = read_required_csv(GE_ADAPTIVE_SUMMARY_PATH)
    fixed = read_required_csv(GE_FIXED_SUMMARY_PATH)

    adaptive = standardize_indicator_id(adaptive)
    fixed = standardize_indicator_id(fixed)
    adaptive = standardize_label_family(adaptive)
    fixed = standardize_label_family(fixed)

    # Keep only relevant columns if present.
    cols_common = ["indicator_id", "label", "family"]
    ge_cols = [
        "n_conditions",
        "median_auroc", "q25_auroc", "q75_auroc",
        "median_auprc", "q25_auprc", "q75_auprc",
        "median_auprc_lift",
        "median_prevalence_pct",
    ]

    a_cols = cols_common + [c for c in ge_cols if c in adaptive.columns]
    f_cols = cols_common + [c for c in ge_cols if c in fixed.columns]

    adaptive = adaptive[a_cols].drop_duplicates("indicator_id")
    fixed = fixed[f_cols].drop_duplicates("indicator_id")

    adaptive = adaptive.rename(columns={
        c: f"adaptive_{c}" for c in adaptive.columns if c not in cols_common
    })
    fixed = fixed.rename(columns={
        c: f"fixed_7m_{c}" for c in fixed.columns if c not in cols_common
    })

    comp = summary[[
        "indicator_id", "label", "family",
        "robustness_index",
        "median_aligned_association",
        "direction_consistency_pct",
        "coverage_fraction",
    ]].merge(
        adaptive,
        on=["indicator_id", "label", "family"],
        how="left",
    ).merge(
        fixed,
        on=["indicator_id", "label", "family"],
        how="left",
    )

    if "adaptive_median_auroc" in comp.columns and "fixed_7m_median_auroc" in comp.columns:
        comp["delta_fixed_7m_minus_adaptive_median_auroc"] = (
            comp["fixed_7m_median_auroc"] - comp["adaptive_median_auroc"]
        )

    if "adaptive_median_auprc" in comp.columns and "fixed_7m_median_auprc" in comp.columns:
        comp["delta_fixed_7m_minus_adaptive_median_auprc"] = (
            comp["fixed_7m_median_auprc"] - comp["adaptive_median_auprc"]
        )

    comp = comp.sort_values("robustness_index", ascending=False).reset_index(drop=True)
    return comp


# ============================================================
# Figure
# ============================================================

def style_axis(ax, grid_axis="x"):
    ax.tick_params(direction="in", top=True, right=True)
    if grid_axis:
        ax.grid(True, axis=grid_axis, color="0.86", linewidth=0.42, alpha=0.75)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_linewidth(0.65)


def draw_panel_a(ax, summary):
    top = summary.head(TOP_N_BARS).copy()
    y = np.arange(len(top))

    ax.barh(
        y,
        top["robustness_index"],
        color=ASSOC_COLOR,
        alpha=0.82,
        edgecolor="black",
        linewidth=0.35,
    )

    ax.set_yticks(y)
    ax.set_yticklabels(top["label"].tolist())
    ax.invert_yaxis()
    ax.set_xlabel("Robustness index")
    ax.set_title("(a) Portable association evidence", loc="left", pad=3)
    ax.xaxis.set_major_locator(MaxNLocator(5))
    style_axis(ax, grid_axis="x")


def draw_panel_b(ax, summary):
    top = summary.head(TOP_N_BARS).copy()
    y = np.arange(len(top))

    ax.scatter(
        top["direction_consistency_pct"],
        y,
        s=28,
        color=ASSOC_COLOR,
        edgecolor="black",
        linewidth=0.35,
        label="Direction consistency",
        zorder=3,
    )

    ax.scatter(
        100.0 * top["coverage_fraction"],
        y,
        s=28,
        color=COVERAGE_COLOR,
        edgecolor="black",
        linewidth=0.35,
        label="Valid-condition coverage",
        zorder=3,
    )

    for yi, row in zip(y, top.itertuples(index=False)):
        ax.plot(
            [100.0 * row.coverage_fraction, row.direction_consistency_pct],
            [yi, yi],
            color="0.72",
            linewidth=0.70,
            zorder=1,
        )

    ax.set_yticks(y)
    ax.set_yticklabels([])
    ax.invert_yaxis()
    ax.set_xlim(0, 103)
    ax.set_xlabel("Percent of conditions (%)")
    ax.set_title("(b) Stability and coverage", loc="left", pad=3)
    ax.legend(loc="lower left", frameon=True, edgecolor="0.80", framealpha=0.95)
    ax.xaxis.set_major_locator(MaxNLocator(5))
    style_axis(ax, grid_axis="x")


def draw_panel_c(ax, by_unit, summary):
    top_ids = summary.head(TOP_N_HEATMAP)["indicator_id"].tolist()
    label_map = summary.set_index("indicator_id")["label"].to_dict()

    units = sorted(by_unit["unit_label"].unique(), key=unit_sort_key)
    unit_labels = [safe_unit_short(u) for u in units]

    mat = (
        by_unit
        .pivot_table(
            index="indicator_id",
            columns="unit_label",
            values="median_aligned_association",
            aggfunc="median",
        )
        .reindex(index=top_ids, columns=units)
    )

    data = mat.to_numpy(dtype=float)
    vmax = np.nanpercentile(data, 95) if np.isfinite(data).any() else 1.0
    vmax = max(vmax, 0.05)

    im = ax.imshow(
        data,
        aspect="auto",
        cmap=HEATMAP_CMAP,
        vmin=0.0,
        vmax=vmax,
    )

    ax.set_xticks(np.arange(len(units)))
    ax.set_xticklabels(unit_labels, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(top_ids)))
    ax.set_yticklabels([label_map.get(iid, iid) for iid in top_ids])
    ax.set_title("(c) Unit-wise median aligned association", loc="left", pad=3)

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data[i, j]
            if np.isfinite(val):
                ax.text(
                    j,
                    i,
                    f"{val:.2f}",
                    ha="center",
                    va="center",
                    fontsize=5.5,
                    color="white" if val > 0.65 * vmax else "black",
                )

    ax.tick_params(direction="in", top=True, right=True)
    for spine in ax.spines.values():
        spine.set_linewidth(0.65)

    cbar = plt.colorbar(im, ax=ax, fraction=0.024, pad=0.012)
    cbar.set_label("Aligned association", fontsize=7.0)
    cbar.ax.tick_params(labelsize=6.3, direction="in")


def draw_panel_d(ax, ge_comp, summary):
    top_ids = summary.head(TOP_N_BARS)["indicator_id"].tolist()
    plot_df = ge_comp[ge_comp["indicator_id"].isin(top_ids)].copy()
    plot_df["indicator_order"] = plot_df["indicator_id"].map({iid: i for i, iid in enumerate(top_ids)})
    plot_df = plot_df.sort_values("indicator_order")

    y = np.arange(len(plot_df))

    a_col = "adaptive_median_auroc"
    f_col = "fixed_7m_median_auroc"

    if a_col not in plot_df.columns or f_col not in plot_df.columns:
        ax.text(0.5, 0.5, "Gross-error comparison not available", ha="center", va="center")
        ax.set_axis_off()
        ax.set_title("(d) Gross-error portability", loc="left", pad=3)
        return

    for yi, row in zip(y, plot_df.itertuples(index=False)):
        a = getattr(row, a_col)
        f = getattr(row, f_col)

        if np.isfinite(a) and np.isfinite(f):
            ax.plot([a, f], [yi, yi], color="0.70", linewidth=0.75, zorder=1)
        if np.isfinite(a):
            ax.scatter(a, yi, s=25, color=GE_ADAPTIVE_COLOR, edgecolor="black", linewidth=0.35, zorder=3)
        if np.isfinite(f):
            ax.scatter(f, yi, s=25, color=GE_FIXED_COLOR, edgecolor="black", linewidth=0.35, zorder=3)

    ax.axvline(0.5, color="0.25", linewidth=0.70, linestyle="--")
    ax.set_yticks(y)
    ax.set_yticklabels(plot_df["label"].tolist())
    ax.invert_yaxis()
    ax.set_xlim(0.45, 0.85)
    ax.set_xlabel("Median AUROC")
    ax.set_title("(d) Adaptive vs fixed 7 m gross-error AUROC", loc="left", pad=3)
    ax.xaxis.set_major_locator(MaxNLocator(5))
    style_axis(ax, grid_axis="x")


def build_figure(summary, by_unit, ge_comp):
    fig = plt.figure(figsize=FIGSIZE)

    gs = fig.add_gridspec(
        nrows=3,
        ncols=2,
        height_ratios=[1.15, 1.60, 1.55],
        width_ratios=[1.20, 0.90],
        hspace=0.40,
        wspace=0.30,
    )

    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, :])
    ax_d = fig.add_subplot(gs[2, :])

    draw_panel_a(ax_a, summary)
    draw_panel_b(ax_b, summary)
    draw_panel_c(ax_c, by_unit, summary)
    draw_panel_d(ax_d, ge_comp, summary)

    handles = [
        Patch(facecolor=GE_ADAPTIVE_COLOR, edgecolor="black", linewidth=0.35, label="Adaptive IQR AUROC"),
        Patch(facecolor=GE_FIXED_COLOR, edgecolor="black", linewidth=0.35, label="Fixed 7 m AUROC"),
    ]

    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.006),
        ncol=2,
        frameon=False,
        handlelength=1.3,
        columnspacing=1.3,
    )

    fig.subplots_adjust(left=0.155, right=0.985, top=0.975, bottom=0.085)

    fig.savefig(OUT_FIG.with_suffix(".png"), dpi=SAVE_DPI, bbox_inches="tight", pad_inches=0.025)
    fig.savefig(OUT_FIG.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.025)
    plt.close(fig)

    print(f"[INFO] Saved figure:\n       {OUT_FIG.with_suffix('.png')}\n       {OUT_FIG.with_suffix('.pdf')}")


# ============================================================
# Main
# ============================================================

def main():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        assoc, robustness_summary = prepare_association_tables()
        by_unit = build_by_unit(assoc, robustness_summary)
        estimator_matrix = build_estimator_matrix(assoc, robustness_summary)
        ge_comparison = build_gross_error_comparison(robustness_summary)

    robustness_summary.to_csv(OUT_SUMMARY, index=False)
    by_unit.to_csv(OUT_BY_UNIT, index=False)
    estimator_matrix.to_csv(OUT_ESTIMATOR, index=False)
    ge_comparison.to_csv(OUT_GE, index=False)

    build_figure(robustness_summary, by_unit, ge_comparison)

    print("\n[INFO] Top cross-dataset robustness indicators:")
    cols = [
        "label",
        "robustness_index",
        "median_aligned_association",
        "direction_consistency_pct",
        "coverage_fraction",
        "n_conditions",
        "n_units",
        "n_estimators",
    ]
    cols = [c for c in cols if c in robustness_summary.columns]
    print(robustness_summary[cols].head(15).to_string(index=False))

    print("\n[INFO] Gross-error comparison for top robust indicators:")
    ge_cols = [
        "label",
        "adaptive_median_auroc",
        "fixed_7m_median_auroc",
        "delta_fixed_7m_minus_adaptive_median_auroc",
        "adaptive_median_auprc",
        "fixed_7m_median_auprc",
    ]
    ge_cols = [c for c in ge_cols if c in ge_comparison.columns]
    print(ge_comparison[ge_cols].head(15).to_string(index=False))

    print("\n[INFO] Wrote tables:")
    for p in [OUT_SUMMARY, OUT_BY_UNIT, OUT_ESTIMATOR, OUT_GE]:
        print(f"       - {p}")

    print("\n[INFO] Done.")


if __name__ == "__main__":
    main()
