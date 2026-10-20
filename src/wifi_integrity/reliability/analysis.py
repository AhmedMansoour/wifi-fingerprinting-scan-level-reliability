"""Condition-level reliability association and gross-error discrimination."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import average_precision_score, roc_auc_score

from wifi_integrity.config import load_yaml
from wifi_integrity.reliability.indicators import add_estimator_specific_nearest_rp

MIN_SCANS = 8
MIN_GROSS = 3
MIN_NORMAL = 3


def _indicator_specs(root: Path) -> list[dict[str, object]]:
    config = load_yaml(root / "config" / "indicators.yaml")
    specs: list[dict[str, object]] = []
    aliases = {"d_cand": "D_cand", "i_k": "I_k", "sqs": "SQS", "c_sigma": "C_sigma", "fii": "FII"}
    for item in config["indicators"]:
        raw_id = str(item["id"])
        indicator_id = aliases.get(raw_id, raw_id)
        adverse = str(item["adverse_direction"])
        expected_sign = 1 if adverse == "high" else -1
        specs.append(
            {
                "indicator_id": indicator_id,
                "label": str(item["label"]),
                "family": str(item["group"]),
                "expected_sign": expected_sign,
            }
        )
    return specs


def _bh_adjust(p_values: pd.Series) -> pd.Series:
    values = pd.to_numeric(p_values, errors="coerce").to_numpy(dtype=float)
    adjusted = np.full(len(values), np.nan)
    valid = np.isfinite(values)
    if not valid.any():
        return pd.Series(adjusted, index=p_values.index)
    p = values[valid]
    order = np.argsort(p)
    ranked = p[order]
    n = len(ranked)
    q = ranked * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0.0, 1.0)
    restored = np.empty(n)
    restored[order] = q
    adjusted[np.flatnonzero(valid)] = restored
    return pd.Series(adjusted, index=p_values.index)


def build_reliability_long_table(root: str | Path) -> pd.DataFrame:
    root_path = Path(root)
    pred = pd.read_csv(
        root_path / "results" / "predictions" / "estimator_predictions_published.csv.gz",
        dtype={"row_id": str},
        low_memory=False,
    )
    pred["unit_label"] = pred["dataset"].astype(str) + " / " + pred["group"].astype(str)
    pred["row_id"] = pred["scan_id"].astype(str).str.split(":", n=1).str[-1]
    pred["estimator_display"] = pred["estimator_label"].astype(str)
    pred["error_m"] = pd.to_numeric(pred["error_2d"], errors="coerce")
    features = pd.read_csv(
        root_path / "results" / "reliability" / "reliability_features_published.csv.gz",
        dtype={"row_id": str},
        low_memory=False,
    )
    keep = [
        "dataset", "group", "unit_label", "row_id", "estimator_family", "estimator_name",
        "estimator_display", "x_true", "y_true", "x_pred", "y_pred", "error_m", "nearest_rp_distance",
    ]
    long_table = pred[keep].merge(
        features,
        on=["dataset", "group", "unit_label", "row_id"],
        how="left",
        validate="many_to_one",
        suffixes=("", "_feature"),
    )
    long_table = add_estimator_specific_nearest_rp(root_path, long_table)
    path = root_path / "results" / "reliability" / "reliability_long_published.csv.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    long_table.to_csv(path, index=False, compression="gzip")
    try:
        long_table.to_parquet(path.with_suffix("").with_suffix(".parquet"), index=False)
    except (ImportError, ModuleNotFoundError, ValueError):
        pass
    return long_table


def compute_association(root: str | Path, long_table: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    root_path = Path(root)
    specs = _indicator_specs(root_path)
    rows: list[dict[str, object]] = []
    for (unit, estimator), group in long_table.groupby(
        ["unit_label", "estimator_display"], observed=False
    ):
        for spec in specs:
            iid = str(spec["indicator_id"])
            subset = pd.DataFrame(
                {
                    "indicator": pd.to_numeric(group[iid], errors="coerce"),
                    "error": pd.to_numeric(group["error_m"], errors="coerce"),
                }
            ).replace([np.inf, -np.inf], np.nan).dropna()
            rho = p_value = np.nan
            if len(subset) >= MIN_SCANS and subset["indicator"].nunique() >= 3:
                result = spearmanr(subset["indicator"], subset["error"])
                rho = float(result.statistic)
                p_value = float(result.pvalue)
            rows.append(
                {
                    "unit_label": unit,
                    "estimator_display": estimator,
                    "indicator_id": iid,
                    "label": spec["label"],
                    "family": spec["family"],
                    "expected_sign": int(spec["expected_sign"]),
                    "n_valid": int(len(subset)),
                    "raw_spearman_rho": rho,
                    "aligned_spearman_rho": int(spec["expected_sign"]) * rho if np.isfinite(rho) else np.nan,
                    "p_value": p_value,
                }
            )
    condition = pd.DataFrame(rows)
    condition["p_value_bh"] = condition.groupby(
        ["unit_label", "estimator_display"], observed=False
    )["p_value"].transform(_bh_adjust)
    condition["significant_bh_q05"] = condition["p_value_bh"] <= 0.05

    summary = (
        condition.groupby(["indicator_id", "label", "family"], observed=False)
        .agg(
            n_conditions=("aligned_spearman_rho", "count"),
            median_aligned_rho=("aligned_spearman_rho", "median"),
            q25_aligned_rho=("aligned_spearman_rho", lambda s: s.quantile(0.25)),
            q75_aligned_rho=("aligned_spearman_rho", lambda s: s.quantile(0.75)),
            direction_consistency_pct=("aligned_spearman_rho", lambda s: 100.0 * (s > 0).mean()),
            significant_conditions_bh=("significant_bh_q05", "sum"),
        )
        .reset_index()
        .sort_values("median_aligned_rho", ascending=False, kind="mergesort")
    )
    table_dir = root_path / "results" / "tables"
    condition.to_csv(table_dir / "reliability_association_by_condition.csv", index=False)
    summary.to_csv(table_dir / "reliability_association_summary_native.csv", index=False)
    return condition, summary


def _condition_thresholds(long_table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (unit, estimator), group in long_table.groupby(
        ["unit_label", "estimator_display"], observed=False
    ):
        error = pd.to_numeric(group["error_m"], errors="coerce").dropna().to_numpy(dtype=float)
        q25, median, q75 = np.percentile(error, [25, 50, 75])
        iqr = q75 - q25
        threshold = q75 + 1.5 * iqr
        gross = error > threshold
        rows.append(
            {
                "unit_label": unit,
                "estimator_display": estimator,
                "n_scans": len(error),
                "q25_error_m": q25,
                "median_error_m": median,
                "q75_error_m": q75,
                "iqr_error_m": iqr,
                "adaptive_threshold_m": threshold,
                "n_gross_error": int(gross.sum()),
                "gross_error_prevalence_pct": 100.0 * gross.mean(),
            }
        )
    return pd.DataFrame(rows)


def _discrimination_for_labels(
    long_table: pd.DataFrame,
    specs: list[dict[str, object]],
    label_col: str,
    strategy: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (unit, estimator), group in long_table.groupby(
        ["unit_label", "estimator_display"], observed=False
    ):
        y = group[label_col].astype(int).to_numpy()
        for spec in specs:
            iid = str(spec["indicator_id"])
            score = int(spec["expected_sign"]) * pd.to_numeric(
                group[iid], errors="coerce"
            ).to_numpy(dtype=float)
            valid = np.isfinite(score) & np.isfinite(y)
            yy, ss = y[valid], score[valid]
            n_pos = int(yy.sum())
            n_neg = int(len(yy) - n_pos)
            if len(yy) < MIN_SCANS or n_pos < MIN_GROSS or n_neg < MIN_NORMAL:
                continue
            auroc = float(roc_auc_score(yy, ss))
            auprc = float(average_precision_score(yy, ss))
            prevalence = n_pos / len(yy)
            rows.append(
                {
                    "strategy": strategy,
                    "unit_label": unit,
                    "estimator_display": estimator,
                    "indicator_id": iid,
                    "label": spec["label"],
                    "family": spec["family"],
                    "n_valid_scans": int(len(yy)),
                    "n_gross_error": n_pos,
                    "n_normal": n_neg,
                    "gross_error_prevalence_pct": 100.0 * prevalence,
                    "auroc": auroc,
                    "auprc": auprc,
                    "auprc_baseline": prevalence,
                    "auprc_lift": auprc / prevalence if prevalence > 0 else np.nan,
                }
            )
    return pd.DataFrame(rows)


def compute_discrimination(
    root: str | Path, long_table: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root)
    specs = _indicator_specs(root_path)
    thresholds = _condition_thresholds(long_table)
    labeled = long_table.merge(
        thresholds[["unit_label", "estimator_display", "adaptive_threshold_m"]],
        on=["unit_label", "estimator_display"],
        how="left",
        validate="many_to_one",
    )
    labeled["gross_error_adaptive"] = (
        labeled["error_m"] > labeled["adaptive_threshold_m"]
    ).astype(int)
    labeled["gross_error_fixed7m"] = (labeled["error_m"] > 7.0).astype(int)
    adaptive = _discrimination_for_labels(
        labeled, specs, "gross_error_adaptive", "adaptive_iqr"
    )
    fixed = _discrimination_for_labels(labeled, specs, "gross_error_fixed7m", "fixed_7m")
    by_condition = pd.concat([adaptive, fixed], ignore_index=True)
    summary = (
        by_condition.groupby(["strategy", "indicator_id", "label", "family"], observed=False)
        .agg(
            n_conditions=("auroc", "count"),
            median_auroc=("auroc", "median"),
            q25_auroc=("auroc", lambda s: s.quantile(0.25)),
            q75_auroc=("auroc", lambda s: s.quantile(0.75)),
            median_auprc=("auprc", "median"),
            q25_auprc=("auprc", lambda s: s.quantile(0.25)),
            q75_auprc=("auprc", lambda s: s.quantile(0.75)),
            median_auprc_lift=("auprc_lift", "median"),
            median_prevalence_pct=("gross_error_prevalence_pct", "median"),
        )
        .reset_index()
    )
    table_dir = root_path / "results" / "tables"
    thresholds.to_csv(table_dir / "gross_error_thresholds_native.csv", index=False)
    by_condition.to_csv(table_dir / "gross_error_discrimination_by_condition.csv", index=False)
    summary.to_csv(table_dir / "gross_error_discrimination_summary_native.csv", index=False)
    labeled.to_csv(
        root_path / "results" / "reliability" / "reliability_decisions_published.csv.gz",
        index=False,
        compression="gzip",
    )
    return thresholds, by_condition, summary


def materialize_approved_reliability_summaries(root: str | Path) -> dict[str, str]:
    """Copy approved revision summaries into result space with explicit provenance."""
    root_path = Path(root)
    source_root = root_path / "reference" / "approved" / "revision_summaries"
    target = root_path / "results" / "tables" / "approved_reliability"
    target.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    for path in sorted(source_root.rglob("*.csv")):
        destination = target / f"{path.parent.name}_{path.name}"
        destination.write_bytes(path.read_bytes())
        mapping[str(path.relative_to(root_path))] = str(destination.relative_to(root_path))
    for path in sorted(source_root.rglob("*.json")):
        destination = target / f"{path.parent.name}_{path.name}"
        destination.write_bytes(path.read_bytes())
        mapping[str(path.relative_to(root_path))] = str(destination.relative_to(root_path))
    (target / "PROVENANCE.json").write_text(
        json.dumps(
            {
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "mode": "published_reference_replay",
                "description": "Approved revision summaries copied without numerical modification.",
                "files": mapping,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return mapping


def run_reliability_analysis(root: str | Path) -> dict[str, object]:
    root_path = Path(root)
    long_table = build_reliability_long_table(root_path)
    association_condition, association_summary = compute_association(root_path, long_table)
    thresholds, discrimination_condition, discrimination_summary = compute_discrimination(
        root_path, long_table
    )
    approved = materialize_approved_reliability_summaries(root_path)

    approved_assoc = pd.read_csv(
        root_path
        / "reference"
        / "approved"
        / "revision_summaries"
        / "A3"
        / "A3_indicator_error_association_summary_ci_bh.csv"
    )
    comparison = association_summary.merge(
        approved_assoc[["indicator_id", "median_aligned_rho"]].rename(
            columns={"median_aligned_rho": "approved_median_aligned_rho"}
        ),
        on="indicator_id",
        how="outer",
    )
    comparison["abs_difference"] = (
        comparison["median_aligned_rho"] - comparison["approved_median_aligned_rho"]
    ).abs()
    comparison.to_csv(
        root_path / "results" / "tables" / "reliability_association_regression.csv",
        index=False,
    )

    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "condition_tables": "native_recomputation",
            "approved_ci_sensitivity_runtime_floor_and_confidently_wrong_summaries": "published_reference_replay",
        },
        "long_rows": int(len(long_table)),
        "association_condition_rows": int(len(association_condition)),
        "valid_association_tests": int(association_condition["raw_spearman_rho"].notna().sum()),
        "discrimination_condition_rows": int(len(discrimination_condition)),
        "threshold_conditions": int(len(thresholds)),
        "approved_summary_files": int(len(approved)),
        "max_abs_association_median_difference": float(comparison["abs_difference"].max()),
    }
    report_path = root_path / "results" / "logs" / "reliability_analysis_regression_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
