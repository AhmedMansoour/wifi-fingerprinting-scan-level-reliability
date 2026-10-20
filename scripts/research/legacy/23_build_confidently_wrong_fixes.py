# ============================================================
# Build confidently-wrong fixes analysis
#
# Save as:
#   src/23_build_confidently_wrong_fixes.py
#
# Run from project root:
# Historical local working directory omitted; use WIFI_RESEARCH_ROOT.
#   %run src/23_build_confidently_wrong_fixes.py
#
# Purpose:
#   This script supports:
#
#       \subsection{Confidently Wrong Fixes}
#       \label{sec:confwrong}
#
#   It tests whether some scans look reliable according to direct
#   RSS-match evidence but are still gross-error cases. This is the
#   failure mode that supports the paper's main integrity argument:
#   high RSS similarity is not equivalent to positioning reliability.
#
# Inputs:
#   data/processed/all_estimator_predictions_10like_units_plus_catboost.csv.gz
#   data/processed/scan_level_reliability_indicator_features.csv.gz
#   data/interim/datasets_combined_all/combined_all_datasets.csv
#
# Required previous script:
#   src/21_build_gross_error_discrimination.py
#
# Outputs:
#   results/figures/fig_confidently_wrong_fixes.png
#   results/figures/fig_confidently_wrong_fixes.pdf
#
#   results/tables/confidently_wrong_summary_by_strategy.csv
#   results/tables/confidently_wrong_by_condition.csv
#   results/tables/confidently_wrong_confidence_quartile_error_rates.csv
#   results/tables/confidently_wrong_indicator_discrimination_by_condition.csv
#   results/tables/confidently_wrong_indicator_discrimination_summary.csv
#   results/tables/confidently_wrong_indicator_shift_by_condition.csv
#   results/tables/confidently_wrong_indicator_shift_summary.csv
#   results/tables/confidently_wrong_rss_confidence_components.csv
#
# Definitions:
#   - Nominal RSS-match confidence is computed from direct match evidence.
#   - A nominally confident scan is in the top quartile of RSS-match
#     confidence within its evaluation unit.
#   - A confidently wrong fix is:
#
#         nominally confident AND gross-error
#
#     where gross-error is evaluated under both:
#       (i)  condition-adaptive upper-tail labels
#       (ii) fixed 7 m labels
# ============================================================

import os
from pathlib import Path
import importlib.util
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator


# ============================================================
# Paths and settings
# ============================================================

ROOT = Path(os.environ.get("WIFI_RESEARCH_ROOT", Path(__file__).resolve().parents[3] / "results/research_workspace")).resolve()
SRC_21 = ROOT / "src" / "21_build_gross_error_discrimination.py"

FIG_DIR = ROOT / "results" / "figures"
TABLE_DIR = ROOT / "results" / "tables"

FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

FIXED_THRESHOLD_M = 7.0
CONFIDENT_QUANTILE = 0.75

SAVE_DPI = 500
FIGSIZE = (7.25, 8.50)

ADAPTIVE_SLUG = "adaptive_iqr"
FIXED_SLUG = "fixed_7m"

STRATEGY_LABELS = {
    ADAPTIVE_SLUG: "Adaptive IQR",
    FIXED_SLUG: "Fixed 7 m",
}

STRATEGY_COLORS = {
    ADAPTIVE_SLUG: "#0072B2",
    FIXED_SLUG: "#D55E00",
}

# Direct RSS-match evidence used to define nominal confidence.
# direction_for_confidence:
#   +1: larger value means stronger nominal match confidence
#   -1: smaller value means stronger nominal match confidence
RSS_CONFIDENCE_COMPONENTS = [
    {"id": "FII", "label": "FII", "direction_for_confidence": +1},
    {"id": "C_sigma", "label": r"$C/\sigma$", "direction_for_confidence": +1},
    {"id": "ap_overlap", "label": "AP overlap", "direction_for_confidence": +1},
    {"id": "mean_ap_overlap", "label": "Mean AP overlap", "direction_for_confidence": +1},
    {"id": "max_cosine_similarity", "label": "Max cosine similarity", "direction_for_confidence": +1},
    {"id": "nearest_match_isolation", "label": "Nearest-match isolation", "direction_for_confidence": +1},
    {"id": "min_rss_distance", "label": "Min RSS distance", "direction_for_confidence": -1},
    {"id": "ap_set_novelty", "label": "AP-set novelty", "direction_for_confidence": -1},
]

# Indicators tested for revealing hidden risk among nominally confident scans.
# They are intentionally richer than direct RSS-match confidence alone.
RISK_INDICATOR_IDS = [
    "SQS",
    "sigma_fps",
    "rss_gradient_proxy",
    "I_k",
    "D_cand",
    "nearest_rp_distance",
    "local_rp_density",
    "ap_count",
    "rss_std",
    "rss_range",
]

MIN_CONFIDENT_SCANS_FOR_METRIC = 20
MIN_CW_CASES = 3
MIN_CC_CASES = 3

TOP_N_PLOT = 10


# ============================================================
# Plot defaults
# ============================================================

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
# Load gross-error module
# ============================================================

def load_ge_module():
    if not SRC_21.exists():
        raise FileNotFoundError(
            f"Cannot find required script:\n{SRC_21}\n"
            "Put 21_build_gross_error_discrimination.py in src/ first."
        )

    spec = importlib.util.spec_from_file_location("gross_error_module", SRC_21)
    ge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ge)
    return ge


# ============================================================
# Helper functions
# ============================================================

def finite_series(s):
    return pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan)


def q25(x):
    x = pd.to_numeric(pd.Series(x), errors="coerce").dropna()
    return float(np.percentile(x, 25)) if len(x) else np.nan


def q75(x):
    x = pd.to_numeric(pd.Series(x), errors="coerce").dropna()
    return float(np.percentile(x, 75)) if len(x) else np.nan


def pct(num, den):
    return 100.0 * num / den if den and den > 0 else np.nan


def make_fixed_thresholds(long_df: pd.DataFrame, ge, fixed_threshold_m: float) -> pd.DataFrame:
    rows = []

    for (unit, est), g in long_df.groupby(["unit_label", "estimator_display"], observed=False):
        err = finite_series(g["error_m"]).dropna().to_numpy(dtype=float)
        if len(err) == 0:
            continue

        gross = err > fixed_threshold_m
        n = int(len(err))
        n_gross = int(gross.sum())

        q25_error = float(np.percentile(err, 25))
        q50_error = float(np.percentile(err, 50))
        q75_error = float(np.percentile(err, 75))
        iqr_error = q75_error - q25_error

        rows.append({
            "unit_label": unit,
            "unit_short": ge.UNIT_SHORT.get(unit, unit),
            "estimator_display": est,
            "estimator_short": ge.ESTIMATOR_SHORT.get(est, est),
            "n_scans": n,
            "q25_error_m": q25_error,
            "median_error_m": q50_error,
            "q75_error_m": q75_error,
            "iqr_error_m": iqr_error,
            # Keep this name so ge.attach_gross_error_labels can be reused.
            "adaptive_threshold_m": float(fixed_threshold_m),
            "threshold_scheme": f"fixed_{fixed_threshold_m:g}m",
            "fixed_threshold_m": float(fixed_threshold_m),
            "n_gross_error": n_gross,
            "gross_error_prevalence_pct": pct(n_gross, n),
        })

    thresholds = pd.DataFrame(rows)
    thresholds["unit_order"] = thresholds["unit_label"].map(ge.unit_sort_key)
    thresholds["estimator_order"] = thresholds["estimator_display"].map(
        lambda e: ge.ESTIMATOR_ORDER.index(e) if e in ge.ESTIMATOR_ORDER else 999
    )
    thresholds = thresholds.sort_values(["unit_order", "estimator_order"])
    thresholds = thresholds.drop(columns=["unit_order", "estimator_order"])

    return thresholds


def component_audit_table(long_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in RSS_CONFIDENCE_COMPONENTS:
        iid = c["id"]
        rows.append({
            "component_id": iid,
            "label": c["label"],
            "direction_for_confidence": c["direction_for_confidence"],
            "available": iid in long_df.columns,
            "nonmissing_fraction": float(finite_series(long_df[iid]).notna().mean()) if iid in long_df.columns else 0.0,
        })
    return pd.DataFrame(rows)


def add_nominal_rss_match_confidence(long_df: pd.DataFrame) -> pd.DataFrame:
    """Compute unit-wise RSS-match confidence from direct signal-match evidence.

    The score is the mean percentile rank of available confidence components.
    Higher score means stronger nominal match confidence.
    """
    long_df = long_df.copy()

    key_cols = ["dataset", "group", "unit_label", "row_id"]
    comp_ids = [c["id"] for c in RSS_CONFIDENCE_COMPONENTS if c["id"] in long_df.columns]

    if not comp_ids:
        raise RuntimeError(
            "None of the RSS confidence components are available. "
            "Check the scan-level feature table."
        )

    scan_df = long_df[key_cols + comp_ids].drop_duplicates(key_cols).copy()

    rank_cols = []
    for comp in RSS_CONFIDENCE_COMPONENTS:
        iid = comp["id"]
        if iid not in scan_df.columns:
            continue

        direction = comp["direction_for_confidence"]
        rank_col = f"rss_conf_rank_{iid}"

        # Unit-wise percentile rank; larger means stronger nominal confidence.
        scan_df[rank_col] = np.nan
        for unit, idx in scan_df.groupby("unit_label", observed=False).groups.items():
            raw = finite_series(scan_df.loc[idx, iid])
            score = direction * raw
            scan_df.loc[idx, rank_col] = score.rank(pct=True, method="average")

        rank_cols.append(rank_col)

    scan_df["rss_match_confidence"] = scan_df[rank_cols].mean(axis=1, skipna=True)

    # Unit-wise confidence percentile and top-quartile label.
    scan_df["rss_match_confidence_percentile"] = np.nan
    scan_df["nominally_confident"] = 0
    scan_df["rss_confidence_quartile"] = np.nan
    scan_df["rss_confidence_threshold_q75"] = np.nan

    for unit, idx in scan_df.groupby("unit_label", observed=False).groups.items():
        conf = finite_series(scan_df.loc[idx, "rss_match_confidence"])

        if conf.notna().sum() == 0:
            continue

        threshold = float(np.nanquantile(conf.to_numpy(dtype=float), CONFIDENT_QUANTILE))
        percentile = conf.rank(pct=True, method="average")

        scan_df.loc[idx, "rss_match_confidence_percentile"] = percentile
        scan_df.loc[idx, "rss_confidence_threshold_q75"] = threshold
        scan_df.loc[idx, "nominally_confident"] = (conf >= threshold).astype(int)

        quartile = np.ceil(percentile * 4.0)
        quartile = quartile.clip(lower=1, upper=4)
        scan_df.loc[idx, "rss_confidence_quartile"] = quartile.astype("Int64")

    merge_cols = key_cols + [
        "rss_match_confidence",
        "rss_match_confidence_percentile",
        "rss_confidence_threshold_q75",
        "rss_confidence_quartile",
        "nominally_confident",
    ]

    long_df = long_df.merge(
        scan_df[merge_cols],
        on=key_cols,
        how="left",
        validate="many_to_one",
    )

    long_df["nominally_confident"] = long_df["nominally_confident"].fillna(0).astype(int)

    print("[INFO] RSS-match confidence components used:")
    for c in RSS_CONFIDENCE_COMPONENTS:
        if c["id"] in comp_ids:
            print(f"       - {c['id']} ({c['label']})")

    return long_df


def get_risk_specs(ge, long_df):
    specs = []
    spec_by_id = {s["id"]: s for s in ge.INDICATOR_SPECS}

    for iid in RISK_INDICATOR_IDS:
        if iid not in long_df.columns:
            continue
        if iid not in spec_by_id:
            continue
        specs.append(spec_by_id[iid])

    if not specs:
        raise RuntimeError("No risk indicators available for confidently-wrong analysis.")

    return specs


def attach_strategy_labels(long_df: pd.DataFrame, thresholds: pd.DataFrame, strategy: str, ge) -> pd.DataFrame:
    labeled = ge.attach_gross_error_labels(long_df.copy(), thresholds)
    labeled["strategy"] = strategy
    labeled["strategy_label"] = STRATEGY_LABELS[strategy]
    labeled["confidently_wrong"] = (
        (labeled["nominally_confident"].astype(int) == 1) &
        (labeled["gross_error"].astype(int) == 1)
    ).astype(int)
    labeled["confidently_correct"] = (
        (labeled["nominally_confident"].astype(int) == 1) &
        (labeled["gross_error"].astype(int) == 0)
    ).astype(int)
    return labeled


# ============================================================
# Tables
# ============================================================

def compute_by_condition(labeled_all: pd.DataFrame, ge) -> pd.DataFrame:
    rows = []

    for (strategy, unit, est), g in labeled_all.groupby(
        ["strategy", "unit_label", "estimator_display"],
        observed=False,
    ):
        n = int(len(g))
        n_gross = int(g["gross_error"].sum())
        n_conf = int(g["nominally_confident"].sum())
        n_cw = int(g["confidently_wrong"].sum())
        n_cc = int(g["confidently_correct"].sum())

        rows.append({
            "strategy": strategy,
            "strategy_label": STRATEGY_LABELS[strategy],
            "unit_label": unit,
            "unit_short": ge.UNIT_SHORT.get(unit, unit),
            "estimator_display": est,
            "estimator_short": ge.ESTIMATOR_SHORT.get(est, est),
            "n_scans": n,
            "n_gross_error": n_gross,
            "gross_error_prevalence_pct": pct(n_gross, n),
            "n_nominally_confident": n_conf,
            "nominally_confident_pct": pct(n_conf, n),
            "n_confidently_wrong": n_cw,
            "n_confidently_correct": n_cc,
            "confidently_wrong_all_pct": pct(n_cw, n),
            "confidently_wrong_among_gross_pct": pct(n_cw, n_gross),
            "confidently_wrong_among_confident_pct": pct(n_cw, n_conf),
        })

    out = pd.DataFrame(rows)
    out["unit_order"] = out["unit_label"].map(ge.unit_sort_key)
    out["estimator_order"] = out["estimator_display"].map(
        lambda e: ge.ESTIMATOR_ORDER.index(e) if e in ge.ESTIMATOR_ORDER else 999
    )
    out["strategy_order"] = out["strategy"].map({ADAPTIVE_SLUG: 0, FIXED_SLUG: 1})
    out = out.sort_values(["strategy_order", "unit_order", "estimator_order"])
    out = out.drop(columns=["strategy_order", "unit_order", "estimator_order"])

    return out


def compute_summary_by_strategy(by_condition: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for strategy, g in by_condition.groupby("strategy", observed=False):
        rows.append({
            "strategy": strategy,
            "strategy_label": STRATEGY_LABELS[strategy],
            "n_conditions": int(len(g)),
            "median_gross_error_prevalence_pct": float(np.nanmedian(g["gross_error_prevalence_pct"])),
            "q25_gross_error_prevalence_pct": q25(g["gross_error_prevalence_pct"]),
            "q75_gross_error_prevalence_pct": q75(g["gross_error_prevalence_pct"]),
            "median_nominally_confident_pct": float(np.nanmedian(g["nominally_confident_pct"])),
            "median_confidently_wrong_all_pct": float(np.nanmedian(g["confidently_wrong_all_pct"])),
            "q25_confidently_wrong_all_pct": q25(g["confidently_wrong_all_pct"]),
            "q75_confidently_wrong_all_pct": q75(g["confidently_wrong_all_pct"]),
            "max_confidently_wrong_all_pct": float(np.nanmax(g["confidently_wrong_all_pct"])),
            "median_confidently_wrong_among_gross_pct": float(np.nanmedian(g["confidently_wrong_among_gross_pct"])),
            "q25_confidently_wrong_among_gross_pct": q25(g["confidently_wrong_among_gross_pct"]),
            "q75_confidently_wrong_among_gross_pct": q75(g["confidently_wrong_among_gross_pct"]),
            "median_confidently_wrong_among_confident_pct": float(np.nanmedian(g["confidently_wrong_among_confident_pct"])),
            "q25_confidently_wrong_among_confident_pct": q25(g["confidently_wrong_among_confident_pct"]),
            "q75_confidently_wrong_among_confident_pct": q75(g["confidently_wrong_among_confident_pct"]),
            "max_confidently_wrong_among_confident_pct": float(np.nanmax(g["confidently_wrong_among_confident_pct"])),
        })

    return pd.DataFrame(rows)


def compute_quartile_error_rates(labeled_all: pd.DataFrame, ge) -> pd.DataFrame:
    rows = []

    for (strategy, unit, est, q), g in labeled_all.groupby(
        ["strategy", "unit_label", "estimator_display", "rss_confidence_quartile"],
        observed=False,
    ):
        if pd.isna(q):
            continue

        n = int(len(g))
        n_gross = int(g["gross_error"].sum())

        rows.append({
            "strategy": strategy,
            "strategy_label": STRATEGY_LABELS[strategy],
            "unit_label": unit,
            "unit_short": ge.UNIT_SHORT.get(unit, unit),
            "estimator_display": est,
            "estimator_short": ge.ESTIMATOR_SHORT.get(est, est),
            "rss_confidence_quartile": int(q),
            "n_scans": n,
            "n_gross_error": n_gross,
            "gross_error_prevalence_pct": pct(n_gross, n),
        })

    out = pd.DataFrame(rows)
    return out.sort_values(["strategy", "unit_label", "estimator_display", "rss_confidence_quartile"])


def compute_confident_indicator_discrimination(labeled_all: pd.DataFrame, risk_specs, ge):
    rows = []

    for spec in risk_specs:
        iid = spec["id"]
        sign = spec["expected_sign"]

        labeled_all[f"risk_score_{iid}"] = sign * finite_series(labeled_all[iid])

        for (strategy, unit, est), g in labeled_all.groupby(
            ["strategy", "unit_label", "estimator_display"],
            observed=False,
        ):
            sub = g[g["nominally_confident"].astype(int) == 1].copy()

            if len(sub) < MIN_CONFIDENT_SCANS_FOR_METRIC:
                continue

            y = sub["gross_error"].astype(int)
            n_cw = int(y.sum())
            n_cc = int((1 - y).sum())

            if n_cw < MIN_CW_CASES or n_cc < MIN_CC_CASES:
                continue

            metrics = ge.compute_auc_metrics(y, sub[f"risk_score_{iid}"])
            if metrics is None:
                continue

            rows.append({
                "strategy": strategy,
                "strategy_label": STRATEGY_LABELS[strategy],
                "indicator_id": iid,
                "label": spec["label"],
                "family": spec["family"],
                "unit_label": unit,
                "unit_short": ge.UNIT_SHORT.get(unit, unit),
                "estimator_display": est,
                "estimator_short": ge.ESTIMATOR_SHORT.get(est, est),
                "n_nominally_confident": int(len(sub)),
                "n_confidently_wrong": n_cw,
                "n_confidently_correct": n_cc,
                "confidently_wrong_among_confident_pct": pct(n_cw, len(sub)),
                **metrics,
            })

    out = pd.DataFrame(rows)

    if out.empty:
        return out, out

    out["unit_order"] = out["unit_label"].map(ge.unit_sort_key)
    out["estimator_order"] = out["estimator_display"].map(
        lambda e: ge.ESTIMATOR_ORDER.index(e) if e in ge.ESTIMATOR_ORDER else 999
    )
    out["strategy_order"] = out["strategy"].map({ADAPTIVE_SLUG: 0, FIXED_SLUG: 1})
    out = out.sort_values(["strategy_order", "indicator_id", "unit_order", "estimator_order"])
    out = out.drop(columns=["strategy_order", "unit_order", "estimator_order"])

    summary = (
        out.groupby(["strategy", "strategy_label", "indicator_id", "label", "family"], observed=False)
        .agg(
            n_conditions=("auroc", "count"),
            median_auroc=("auroc", "median"),
            q25_auroc=("auroc", q25),
            q75_auroc=("auroc", q75),
            median_auprc=("auprc", "median"),
            q25_auprc=("auprc", q25),
            q75_auprc=("auprc", q75),
            median_auprc_lift=("auprc_lift", "median"),
            median_confidently_wrong_among_confident_pct=("confidently_wrong_among_confident_pct", "median"),
        )
        .reset_index()
    )

    summary["strategy_order"] = summary["strategy"].map({ADAPTIVE_SLUG: 0, FIXED_SLUG: 1})
    summary = summary.sort_values(["strategy_order", "median_auroc"], ascending=[True, False])
    summary = summary.drop(columns=["strategy_order"])

    return out, summary


def compute_indicator_shift(labeled_all: pd.DataFrame, risk_specs, ge):
    rows = []

    for spec in risk_specs:
        iid = spec["id"]
        sign = spec["expected_sign"]
        risk_col = f"risk_score_{iid}"
        rank_col = f"risk_percentile_{iid}"

        labeled_all[risk_col] = sign * finite_series(labeled_all[iid])
        labeled_all[rank_col] = np.nan

        for (strategy, unit, est), idx in labeled_all.groupby(
            ["strategy", "unit_label", "estimator_display"],
            observed=False,
        ).groups.items():
            score = finite_series(labeled_all.loc[idx, risk_col])
            labeled_all.loc[idx, rank_col] = score.rank(pct=True, method="average")

        for (strategy, unit, est), g in labeled_all.groupby(
            ["strategy", "unit_label", "estimator_display"],
            observed=False,
        ):
            sub = g[g["nominally_confident"].astype(int) == 1].copy()
            cw = sub[sub["confidently_wrong"].astype(int) == 1]
            cc = sub[sub["confidently_correct"].astype(int) == 1]

            if len(cw) < MIN_CW_CASES or len(cc) < MIN_CC_CASES:
                continue

            cw_rank = finite_series(cw[rank_col]).dropna()
            cc_rank = finite_series(cc[rank_col]).dropna()
            cw_raw = finite_series(cw[risk_col]).dropna()
            cc_raw = finite_series(cc[risk_col]).dropna()

            if len(cw_rank) < MIN_CW_CASES or len(cc_rank) < MIN_CC_CASES:
                continue

            rows.append({
                "strategy": strategy,
                "strategy_label": STRATEGY_LABELS[strategy],
                "indicator_id": iid,
                "label": spec["label"],
                "family": spec["family"],
                "unit_label": unit,
                "unit_short": ge.UNIT_SHORT.get(unit, unit),
                "estimator_display": est,
                "estimator_short": ge.ESTIMATOR_SHORT.get(est, est),
                "n_confidently_wrong": int(len(cw_rank)),
                "n_confidently_correct": int(len(cc_rank)),
                "median_risk_percentile_confidently_wrong": float(np.nanmedian(cw_rank)),
                "median_risk_percentile_confidently_correct": float(np.nanmedian(cc_rank)),
                "delta_median_risk_percentile": float(np.nanmedian(cw_rank) - np.nanmedian(cc_rank)),
                "median_aligned_risk_score_confidently_wrong": float(np.nanmedian(cw_raw)) if len(cw_raw) else np.nan,
                "median_aligned_risk_score_confidently_correct": float(np.nanmedian(cc_raw)) if len(cc_raw) else np.nan,
                "delta_median_aligned_risk_score": (
                    float(np.nanmedian(cw_raw) - np.nanmedian(cc_raw)) if len(cw_raw) and len(cc_raw) else np.nan
                ),
            })

    out = pd.DataFrame(rows)

    if out.empty:
        return out, out

    summary = (
        out.groupby(["strategy", "strategy_label", "indicator_id", "label", "family"], observed=False)
        .agg(
            n_conditions=("delta_median_risk_percentile", "count"),
            median_delta_risk_percentile=("delta_median_risk_percentile", "median"),
            q25_delta_risk_percentile=("delta_median_risk_percentile", q25),
            q75_delta_risk_percentile=("delta_median_risk_percentile", q75),
            positive_shift_pct=("delta_median_risk_percentile", lambda x: 100.0 * np.mean(pd.to_numeric(x, errors="coerce") > 0)),
            median_risk_percentile_confidently_wrong=("median_risk_percentile_confidently_wrong", "median"),
            median_risk_percentile_confidently_correct=("median_risk_percentile_confidently_correct", "median"),
        )
        .reset_index()
    )

    summary["strategy_order"] = summary["strategy"].map({ADAPTIVE_SLUG: 0, FIXED_SLUG: 1})
    summary = summary.sort_values(["strategy_order", "median_delta_risk_percentile"], ascending=[True, False])
    summary = summary.drop(columns=["strategy_order"])

    return out, summary


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


def draw_panel_a(ax, by_condition):
    data = []
    positions = []
    colors = []
    labels = []

    for i, strategy in enumerate([ADAPTIVE_SLUG, FIXED_SLUG]):
        vals = finite_series(
            by_condition.loc[
                by_condition["strategy"] == strategy,
                "confidently_wrong_among_confident_pct",
            ]
        ).dropna().to_numpy(dtype=float)
        data.append(vals)
        positions.append(i)
        colors.append(STRATEGY_COLORS[strategy])
        labels.append(STRATEGY_LABELS[strategy])

    bp = ax.boxplot(
        data,
        positions=positions,
        widths=0.42,
        patch_artist=True,
        showfliers=True,
        medianprops={"color": "black", "linewidth": 0.85},
        whiskerprops={"color": "0.35", "linewidth": 0.70},
        capprops={"color": "0.35", "linewidth": 0.70},
        boxprops={"edgecolor": "0.30", "linewidth": 0.65},
        flierprops={"marker": "o", "markersize": 2.4, "markerfacecolor": "0.6", "markeredgewidth": 0.0, "alpha": 0.55},
    )

    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.70)

    rng = np.random.default_rng(2026)
    for x0, vals, color in zip(positions, data, colors):
        if len(vals) == 0:
            continue
        jitter = rng.uniform(-0.10, 0.10, size=len(vals))
        ax.scatter(
            np.full_like(vals, x0, dtype=float) + jitter,
            vals,
            s=8,
            color=color,
            alpha=0.38,
            edgecolor="none",
            zorder=3,
        )

    ax.set_xticks(positions)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Confidently wrong among\nnominally confident scans (%)")
    ax.set_title("(a) Confidently wrong prevalence", loc="left", pad=3)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    style_axis(ax, grid_axis="y")


def draw_panel_b(ax, quartile_rates):
    summary = (
        quartile_rates.groupby(["strategy", "rss_confidence_quartile"], observed=False)
        .agg(
            median=("gross_error_prevalence_pct", "median"),
            q25=("gross_error_prevalence_pct", q25),
            q75=("gross_error_prevalence_pct", q75),
        )
        .reset_index()
    )

    x = np.arange(1, 5)

    for strategy in [ADAPTIVE_SLUG, FIXED_SLUG]:
        g = summary[summary["strategy"] == strategy].set_index("rss_confidence_quartile").reindex(x)
        y = g["median"].to_numpy(dtype=float)
        lo = g["q25"].to_numpy(dtype=float)
        hi = g["q75"].to_numpy(dtype=float)

        ax.plot(
            x,
            y,
            marker="o",
            linewidth=1.2,
            markersize=3.6,
            color=STRATEGY_COLORS[strategy],
            label=STRATEGY_LABELS[strategy],
        )
        ax.fill_between(
            x,
            lo,
            hi,
            color=STRATEGY_COLORS[strategy],
            alpha=0.14,
            linewidth=0,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(["Q1\nlow", "Q2", "Q3", "Q4\nhigh"])
    ax.set_xlabel("RSS-match confidence quartile")
    ax.set_ylabel("Gross-error prevalence (%)")
    ax.set_title("(b) Gross errors by nominal RSS confidence", loc="left", pad=3)
    ax.legend(loc="upper left", frameon=True, edgecolor="0.80", framealpha=0.95)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    style_axis(ax, grid_axis="y")


def choose_top_indicators(discrimination_summary, shift_summary):
    adaptive = discrimination_summary[discrimination_summary["strategy"] == ADAPTIVE_SLUG].copy()

    if not adaptive.empty:
        top = adaptive.sort_values("median_auroc", ascending=False)["indicator_id"].head(TOP_N_PLOT).tolist()
        return top

    adaptive_shift = shift_summary[shift_summary["strategy"] == ADAPTIVE_SLUG].copy()
    if not adaptive_shift.empty:
        top = adaptive_shift.sort_values("median_delta_risk_percentile", ascending=False)["indicator_id"].head(TOP_N_PLOT).tolist()
        return top

    return []


def draw_paired_dot_panel(ax, summary, value_col, title, xlabel, top_ids):
    if summary.empty or not top_ids:
        ax.text(0.5, 0.5, "No valid conditions", ha="center", va="center")
        ax.set_title(title, loc="left", pad=3)
        ax.axis("off")
        return

    label_map = (
        summary.drop_duplicates("indicator_id")
        .set_index("indicator_id")["label"]
        .to_dict()
    )

    mat = (
        summary[summary["indicator_id"].isin(top_ids)]
        .pivot_table(index="indicator_id", columns="strategy", values=value_col, aggfunc="median")
        .reindex(index=top_ids, columns=[ADAPTIVE_SLUG, FIXED_SLUG])
    )

    y = np.arange(len(mat))

    for idx, iid in enumerate(mat.index):
        a = mat.loc[iid, ADAPTIVE_SLUG]
        f = mat.loc[iid, FIXED_SLUG]

        if np.isfinite(a) and np.isfinite(f):
            ax.plot([a, f], [idx, idx], color="0.70", linewidth=0.75, zorder=1)
        if np.isfinite(a):
            ax.scatter(a, idx, s=24, color=STRATEGY_COLORS[ADAPTIVE_SLUG], edgecolor="black", linewidth=0.35, zorder=3)
        if np.isfinite(f):
            ax.scatter(f, idx, s=24, color=STRATEGY_COLORS[FIXED_SLUG], edgecolor="black", linewidth=0.35, zorder=3)

    ax.set_yticks(y)
    ax.set_yticklabels([label_map.get(iid, iid) for iid in mat.index])
    ax.invert_yaxis()
    ax.set_title(title, loc="left", pad=3)
    ax.set_xlabel(xlabel)
    ax.xaxis.set_major_locator(MaxNLocator(5))
    style_axis(ax, grid_axis="x")


def build_figure(by_condition, quartile_rates, discrimination_summary, shift_summary):
    top_ids = choose_top_indicators(discrimination_summary, shift_summary)

    fig = plt.figure(figsize=FIGSIZE)
    gs = fig.add_gridspec(
        nrows=2,
        ncols=2,
        height_ratios=[0.88, 1.35],
        width_ratios=[0.82, 1.18],
        hspace=0.36,
        wspace=0.48,
    )

    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    draw_panel_a(ax_a, by_condition)
    draw_panel_b(ax_b, quartile_rates)
    draw_paired_dot_panel(
        ax_c,
        shift_summary,
        "median_delta_risk_percentile",
        "(c) Risk-score shift within nominally confident scans",
        "Median percentile shift\n(confidently wrong - confidently correct)",
        top_ids,
    )
    draw_paired_dot_panel(
        ax_d,
        discrimination_summary,
        "median_auroc",
        "(d) Discrimination within nominally confident scans",
        "Median AUROC",
        top_ids,
    )

    handles = [
        Patch(facecolor=STRATEGY_COLORS[ADAPTIVE_SLUG], edgecolor="black", linewidth=0.35, label=STRATEGY_LABELS[ADAPTIVE_SLUG]),
        Patch(facecolor=STRATEGY_COLORS[FIXED_SLUG], edgecolor="black", linewidth=0.35, label=STRATEGY_LABELS[FIXED_SLUG]),
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

    fig.subplots_adjust(left=0.145, right=0.985, top=0.975, bottom=0.085)

    out = FIG_DIR / "fig_confidently_wrong_fixes"
    fig.savefig(out.with_suffix(".png"), dpi=SAVE_DPI, bbox_inches="tight", pad_inches=0.025)
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.025)
    plt.close(fig)

    print(f"[INFO] Saved figure:\n       {out.with_suffix('.png')}\n       {out.with_suffix('.pdf')}")


# ============================================================
# Main
# ============================================================

def main():
    ge = load_ge_module()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        pred, features, combined = ge.load_inputs()
        long_df = ge.build_long_table(pred, features, combined)

    component_audit = component_audit_table(long_df)
    component_audit.to_csv(TABLE_DIR / "confidently_wrong_rss_confidence_components.csv", index=False)

    long_df = add_nominal_rss_match_confidence(long_df)

    adaptive_thresholds = ge.compute_condition_thresholds(long_df)
    adaptive_thresholds["threshold_scheme"] = ADAPTIVE_SLUG

    fixed_thresholds = make_fixed_thresholds(long_df, ge, FIXED_THRESHOLD_M)

    adaptive_labeled = attach_strategy_labels(long_df, adaptive_thresholds, ADAPTIVE_SLUG, ge)
    fixed_labeled = attach_strategy_labels(long_df, fixed_thresholds, FIXED_SLUG, ge)

    labeled_all = pd.concat([adaptive_labeled, fixed_labeled], ignore_index=True)

    risk_specs = get_risk_specs(ge, labeled_all)

    print("[INFO] Risk indicators tested for confidently-wrong exposure:")
    for s in risk_specs:
        print(f"       - {s['id']} ({s['label']})")

    by_condition = compute_by_condition(labeled_all, ge)
    summary_by_strategy = compute_summary_by_strategy(by_condition)
    quartile_rates = compute_quartile_error_rates(labeled_all, ge)

    discrimination_by_condition, discrimination_summary = compute_confident_indicator_discrimination(
        labeled_all.copy(),
        risk_specs,
        ge,
    )

    shift_by_condition, shift_summary = compute_indicator_shift(
        labeled_all.copy(),
        risk_specs,
        ge,
    )

    # Save tables.
    summary_by_strategy.to_csv(TABLE_DIR / "confidently_wrong_summary_by_strategy.csv", index=False)
    by_condition.to_csv(TABLE_DIR / "confidently_wrong_by_condition.csv", index=False)
    quartile_rates.to_csv(TABLE_DIR / "confidently_wrong_confidence_quartile_error_rates.csv", index=False)
    discrimination_by_condition.to_csv(TABLE_DIR / "confidently_wrong_indicator_discrimination_by_condition.csv", index=False)
    discrimination_summary.to_csv(TABLE_DIR / "confidently_wrong_indicator_discrimination_summary.csv", index=False)
    shift_by_condition.to_csv(TABLE_DIR / "confidently_wrong_indicator_shift_by_condition.csv", index=False)
    shift_summary.to_csv(TABLE_DIR / "confidently_wrong_indicator_shift_summary.csv", index=False)

    build_figure(by_condition, quartile_rates, discrimination_summary, shift_summary)

    print("\n[INFO] Summary by strategy:")
    print(summary_by_strategy.to_string(index=False))

    if not discrimination_summary.empty:
        print("\n[INFO] Top confidently-wrong discriminators:")
        cols = [
            "strategy_label",
            "label",
            "median_auroc",
            "q25_auroc",
            "q75_auroc",
            "median_auprc",
            "median_auprc_lift",
            "n_conditions",
        ]
        cols = [c for c in cols if c in discrimination_summary.columns]
        print(discrimination_summary[cols].groupby("strategy_label", group_keys=False).head(10).to_string(index=False))
    else:
        print("\n[WARN] No valid confidently-wrong discrimination metrics were produced.")

    if not shift_summary.empty:
        print("\n[INFO] Top confidently-wrong risk-score shifts:")
        cols = [
            "strategy_label",
            "label",
            "median_delta_risk_percentile",
            "q25_delta_risk_percentile",
            "q75_delta_risk_percentile",
            "positive_shift_pct",
            "n_conditions",
        ]
        cols = [c for c in cols if c in shift_summary.columns]
        print(shift_summary[cols].groupby("strategy_label", group_keys=False).head(10).to_string(index=False))
    else:
        print("\n[WARN] No valid confidently-wrong shift metrics were produced.")

    print("\n[INFO] Wrote tables:")
    for name in [
        "confidently_wrong_summary_by_strategy.csv",
        "confidently_wrong_by_condition.csv",
        "confidently_wrong_confidence_quartile_error_rates.csv",
        "confidently_wrong_indicator_discrimination_by_condition.csv",
        "confidently_wrong_indicator_discrimination_summary.csv",
        "confidently_wrong_indicator_shift_by_condition.csv",
        "confidently_wrong_indicator_shift_summary.csv",
        "confidently_wrong_rss_confidence_components.csv",
    ]:
        print(f"       - {TABLE_DIR / name}")

    print("\n[INFO] Done.")


if __name__ == "__main__":
    main()
