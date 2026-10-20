"""Native estimator execution through the common benchmark interface."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import yaml

from wifi_integrity.benchmark.metrics import condition_summary, overall_summary
from wifi_integrity.estimators.base import load_unit_data
from wifi_integrity.estimators.classical import (
    make_catboost,
    make_extra_trees,
    make_hgb,
    make_random_forest,
)
from wifi_integrity.estimators.retrieval import RetrievalEstimator


_RETRIEVAL_RE = re.compile(r"^(KNN|WKNN)_k(?P<k>\d+)(?:_q(?P<q>\d+))?_(?P<metric>.+)$")


def _registries(root: Path):
    with (root / "config/datasets.yaml").open(encoding="utf-8") as handle:
        datasets = yaml.safe_load(handle)
    by_id = {u["id"]: u for u in datasets["units"]}
    by_source = {(u["dataset"], u["group"]): u for u in datasets["units"]}
    return by_id, by_source


def _retrieval_parameters(root: Path) -> dict[tuple[str, str], dict]:
    pred = pd.read_csv(
        root / "reference/approved/legacy_canonical/estimator_predictions_approved.csv.gz",
        usecols=["dataset", "group", "estimator_display", "estimator_name"],
        low_memory=False,
    ).drop_duplicates()
    _, by_source = _registries(root)
    params = {}
    for row in pred.loc[pred["estimator_display"].isin(["KNN", "WKNN"])].itertuples():
        match = _RETRIEVAL_RE.match(row.estimator_name)
        if not match:
            raise ValueError(f"Cannot parse retrieval estimator name: {row.estimator_name}")
        unit_id = by_source[(row.dataset, row.group)]["id"]
        params[(unit_id, row.estimator_display)] = {
            "k": int(match.group("k")),
            "q": float(match.group("q")) if match.group("q") else None,
            "metric": match.group("metric"),
            "legacy_name": row.estimator_name,
        }
    return params


def make_native_estimator(root: Path, unit_id: str, estimator_id: str):
    if estimator_id in {"knn", "wknn"}:
        label = "KNN" if estimator_id == "knn" else "WKNN"
        p = _retrieval_parameters(root)[(unit_id, label)]
        return RetrievalEstimator(
            estimator_id=estimator_id,
            estimator_label=label,
            k=p["k"],
            metric=p["metric"],
            weight_power=p["q"] if estimator_id == "wknn" else None,
        )
    if estimator_id == "random_forest":
        return make_random_forest()
    if estimator_id == "extra_trees":
        return make_extra_trees()
    if estimator_id == "hgb":
        return make_hgb()
    if estimator_id == "catboost":
        from wifi_integrity.estimators.catboost_model import CatBoostCoordinateEstimator
        return CatBoostCoordinateEstimator()
    if estimator_id in {"transformer_ap", "residual_cnn"}:
        from wifi_integrity.estimators.deep import DeepCoordinateEstimator
        return DeepCoordinateEstimator(estimator_id)
    raise NotImplementedError(
        f"Unknown native estimator {estimator_id!r}. "
        "Use published replay for the exact eight-estimator benchmark."
    )


def run_native_benchmark(
    root: Path,
    *,
    unit_ids: list[str],
    estimator_ids: list[str],
    output_name: str = "estimator_predictions_native.csv.gz",
) -> dict:
    root = root.resolve()
    (root / "results/tables").mkdir(parents=True, exist_ok=True)
    (root / "results/logs").mkdir(parents=True, exist_ok=True)
    registry, _ = _registries(root)
    frames = []
    runs = []
    for unit_id in unit_ids:
        data = load_unit_data(root, unit_id, registry)
        for estimator_id in estimator_ids:
            estimator = make_native_estimator(root, unit_id, estimator_id)
            result = estimator.fit_predict(data)
            frames.append(result.predictions)
            runs.append({
                "unit_id": unit_id,
                "estimator_id": estimator_id,
                "rows": len(result.predictions),
                "mode": result.mode,
            })
    predictions = pd.concat(frames, ignore_index=True)
    out_dir = root / "results/predictions"
    out_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(out_dir / output_name, index=False)
    condition = condition_summary(predictions)
    overall = overall_summary(condition)
    stem = output_name.replace(".csv.gz", "")
    condition.to_csv(root / "results/tables" / f"{stem}_condition_summary.csv", index=False)
    overall.to_csv(root / "results/tables" / f"{stem}_overall_summary.csv", index=False)
    report = {
        "status": "completed",
        "mode": "native",
        "units": unit_ids,
        "estimators": estimator_ids,
        "prediction_rows": len(predictions),
        "runs": runs,
        "output": str(out_dir / output_name),
    }
    (root / "results/logs" / f"{stem}_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report
