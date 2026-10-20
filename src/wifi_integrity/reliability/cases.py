"""Deterministic gross-error case selection and case-atlas data generation."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from wifi_integrity.config import load_yaml


def _robust_unit_interval(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    lo, hi = values.quantile([0.05, 0.95])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return pd.Series(0.5, index=series.index)
    return ((values - lo) / (hi - lo)).clip(0, 1)


def _indicator_warning_flags(group: pd.DataFrame, specs: list[dict[str, object]], budget: float) -> pd.DataFrame:
    out = pd.DataFrame(index=group.index)
    for spec in specs:
        iid = str(spec["indicator_id"])
        aligned = int(spec["expected_sign"]) * pd.to_numeric(group[iid], errors="coerce")
        threshold = aligned.quantile(1.0 - budget)
        out[f"warn_{iid}"] = aligned >= threshold
    return out


def build_case_registry(root: str | Path, n_cases: int = 24) -> dict[str, object]:
    root_path = Path(root)
    decisions = pd.read_csv(
        root_path / "results" / "reliability" / "reliability_decisions_published.csv.gz",
        dtype={"row_id": str},
        low_memory=False,
    )
    indicator_config = load_yaml(root_path / "config" / "indicators.yaml")
    aliases = {"d_cand": "D_cand", "i_k": "I_k", "sqs": "SQS", "c_sigma": "C_sigma", "fii": "FII"}
    specs = []
    for item in indicator_config["indicators"]:
        iid = aliases.get(str(item["id"]), str(item["id"]))
        specs.append(
            {
                "indicator_id": iid,
                "expected_sign": 1 if item["adverse_direction"] == "high" else -1,
            }
        )
    budget = float(load_yaml(root_path / "config" / "analysis.yaml")["case_warning_budget"])

    warning_parts = []
    for _, group in decisions.groupby(["unit_label", "estimator_display"], observed=False):
        warning_parts.append(_indicator_warning_flags(group, specs, budget))
    warnings = pd.concat(warning_parts).sort_index()
    decisions = pd.concat([decisions, warnings], axis=1)
    warning_columns = [column for column in decisions if column.startswith("warn_")]
    decisions["warning_count"] = decisions[warning_columns].sum(axis=1)
    decisions["warning_fraction"] = decisions["warning_count"] / len(warning_columns)

    # SQS low values are the common confidence signal used for four-state cases.
    decisions["sqs_confident"] = False
    for _, index in decisions.groupby(["unit_label", "estimator_display"], observed=False).groups.items():
        threshold = decisions.loc[index, "SQS"].quantile(0.75)
        decisions.loc[index, "sqs_confident"] = decisions.loc[index, "SQS"] >= threshold
    decisions["case_state"] = np.select(
        [
            decisions["gross_error_adaptive"].eq(1) & decisions["sqs_confident"],
            decisions["gross_error_adaptive"].eq(1) & ~decisions["sqs_confident"],
            decisions["gross_error_adaptive"].eq(0) & decisions["sqs_confident"],
        ],
        ["confidently_wrong", "detected_or_low_confidence_gross_error", "confidently_correct"],
        default="other_correct",
    )

    # Deterministic rank scores within each condition.
    decisions["severity_score"] = decisions.groupby(
        ["unit_label", "estimator_display"], observed=False
    )["error_m"].transform(_robust_unit_interval)
    decisions["low_sqs_score"] = decisions.groupby(
        ["unit_label", "estimator_display"], observed=False
    )["SQS"].transform(lambda s: 1.0 - _robust_unit_interval(s))
    decisions["case_score"] = (
        0.45 * decisions["severity_score"]
        + 0.25 * decisions["case_state"].eq("confidently_wrong").astype(float)
        + 0.15 * decisions["warning_fraction"]
        + 0.15 * decisions["low_sqs_score"]
    )

    category_targets = {
        "confidently_wrong": 6,
        "detected_or_low_confidence_gross_error": 8,
        "confidently_correct": 4,
        "other_correct": 2,
    }
    selected_parts = []
    used_keys: set[tuple[str, str]] = set()
    for category, target in category_targets.items():
        candidates = decisions[decisions["case_state"].eq(category)].copy()
        candidates = candidates.sort_values(
            ["case_score", "error_m", "unit_label", "estimator_display", "row_id"],
            ascending=[False, False, True, True, True],
            kind="mergesort",
        )
        rows = []
        per_condition: dict[tuple[str, str], int] = {}
        for _, row in candidates.iterrows():
            condition = (str(row["unit_label"]), str(row["estimator_display"]))
            if per_condition.get(condition, 0) >= 2:
                continue
            rows.append(row)
            per_condition[condition] = per_condition.get(condition, 0) + 1
            used_keys.add(condition)
            if len(rows) >= target:
                break
        if rows:
            selected_parts.append(pd.DataFrame(rows))

    selected = pd.concat(selected_parts, ignore_index=True) if selected_parts else decisions.head(0)
    # Fill remaining slots with globally strongest unique cases.
    if len(selected) < n_cases:
        existing = set(zip(selected["unit_label"], selected["estimator_display"], selected["row_id"]))
        remaining = decisions.sort_values(
            ["case_score", "unit_label", "estimator_display", "row_id"],
            ascending=[False, True, True, True],
            kind="mergesort",
        )
        additions = []
        for _, row in remaining.iterrows():
            key = (row["unit_label"], row["estimator_display"], row["row_id"])
            if key in existing:
                continue
            additions.append(row)
            existing.add(key)
            if len(selected) + len(additions) >= n_cases:
                break
        if additions:
            selected = pd.concat([selected, pd.DataFrame(additions)], ignore_index=True)
    selected = selected.head(n_cases).copy()
    selected.insert(0, "case_id", [f"C{i:03d}" for i in range(1, len(selected) + 1)])

    candidate_table = pd.read_csv(
        root_path / "results" / "reliability" / "diagnostic_candidates_m10.csv.gz",
        dtype={"row_id": str},
    )
    case_candidates = candidate_table.merge(
        selected[["case_id", "dataset", "group", "unit_label", "row_id"]],
        on=["dataset", "group", "unit_label", "row_id"],
        how="inner",
        validate="many_to_many",
    )

    selected_columns = [
        "case_id", "case_state", "case_score", "unit_label", "estimator_display", "row_id",
        "floor", "x_true", "y_true", "x_pred", "y_pred", "error_m",
        "adaptive_threshold_m", "gross_error_adaptive", "gross_error_fixed7m",
        "SQS", "C_sigma", "FII", "warning_count", "warning_fraction",
        "nearest_rp_distance", "sigma_fps", "D_cand", "I_k", "rss_gradient_proxy",
        "min_rss_distance", "ap_overlap", "local_rp_density", "ap_count",
        "diagnostic_x", "diagnostic_y",
    ]
    registry = selected[selected_columns].copy()
    output_dir = root_path / "results" / "cases"
    output_dir.mkdir(parents=True, exist_ok=True)
    registry.to_csv(output_dir / "case_registry.csv", index=False)
    case_candidates.to_csv(output_dir / "case_candidates.csv", index=False)

    # Compact JSON for the offline dashboard.
    cases_json = []
    for _, case in registry.iterrows():
        candidates = case_candidates[case_candidates["case_id"].eq(case["case_id"])].sort_values(
            "candidate_rank"
        )
        item = {
            key: (None if pd.isna(value) else value.item() if hasattr(value, "item") else value)
            for key, value in case.to_dict().items()
        }
        item["candidates"] = candidates[
            ["candidate_rank", "candidate_x", "candidate_y", "candidate_floor", "normalized_rss_distance"]
        ].where(pd.notna(candidates), None).to_dict(orient="records")
        cases_json.append(item)
    (output_dir / "case_atlas.json").write_text(
        json.dumps(cases_json, indent=2, default=str), encoding="utf-8"
    )

    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "selection_mode": "deterministic_weighted_quota",
        "requested_cases": n_cases,
        "selected_cases": int(len(registry)),
        "represented_units": int(registry["unit_label"].nunique()),
        "represented_estimators": int(registry["estimator_display"].nunique()),
        "states": registry["case_state"].value_counts().to_dict(),
        "case_candidate_rows": int(len(case_candidates)),
    }
    (output_dir / "case_selection_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report
