"""Estimator registry and dependency status."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import yaml


def estimator_registry(root: Path) -> pd.DataFrame:
    with (root / "config/estimators.yaml").open(encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    rows = []
    for item in cfg["estimators"]:
        estimator_id = item["id"]
        dependency = "core"
        native_status = "available"
        if estimator_id == "catboost":
            dependency = "catboost"
            native_status = "available" if importlib.util.find_spec("catboost") else "optional dependency missing"
        elif estimator_id == "transformer_ap":
            dependency = "torch"
            native_status = "available" if importlib.util.find_spec("torch") else "optional dependency missing"
        elif estimator_id == "residual_cnn":
            dependency = "tensorflow"
            native_status = "available" if importlib.util.find_spec("tensorflow") else "optional dependency missing"
        rows.append(
            {
                "estimator_id": estimator_id,
                "estimator_label": item["label"],
                "family": item["family"],
                "published_replay": "available",
                "native_adapter": native_status,
                "dependency": dependency,
                "seed": item.get("seed", 42),
            }
        )
    return pd.DataFrame(rows)
